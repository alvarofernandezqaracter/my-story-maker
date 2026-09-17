# §19 Interfaz web. Servidor local de la biblioteca estandar: sirve web/ y
# expone una API pequena sobre el canon y sobre el flujo. No decide nada del
# sistema, igual que la CLI (§18): valida la forma de lo que entra, llama al
# flujo o al canon y devuelve JSON.
#
# El flujo corre en un unico hilo de trabajo y nunca dos a la vez (§8). El
# servidor atiende peticiones mientras tanto para que la pagina pueda contar lo
# que esta pasando, pero eso es HTTP, no dos novelas en paralelo.
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from . import trazas_cc
from .agentes import Agentes, ParadaDelProceso
from .config import cargar_config, ErrorConfig
from .canon import Canon
from .canon_cc import CanonCC, auditar_gate, media_de, notas_en_lista, operacion
from .contexto import generar_contexto
from .flujo import preparar, escribir_capitulo, cerrar, reanudar, siguiente_capitulo
from .gate import gate, media, notas
from .util import numero_corto, redondear

RAIZ_WEB = Path(__file__).resolve().parent.parent / 'web'

# El tipo se resuelve aqui y no con mimetypes: en Windows esa biblioteca lee el
# registro, y un .js declarado text/plain rompe los modulos ES de la escena.
TIPOS = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.woff2': 'font/woff2',
    '.png': 'image/png',
}

CAMPOS_BRIEF = ('epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo')

# El brief se crea sobre un proyecto en blanco. Pisar el de un libro en marcha
# dejaria el canon hablando de otra novela.
ESTADOS_QUE_ACEPTAN_BRIEF = (None, 'borrador')

ACCIONES = ('preparar', 'escribir', 'cerrar', 'reanudar', 'todo')

# Los dos caminos de §1. `delegado` es el principal y lee el canon en ficheros
# de §21; `harness` lee el SQLite de §3. La misma pagina sirve para los dos
# porque la forma de los datos es la misma, y por eso se pueden comparar.
CAMINOS = ('delegado', 'harness')

# Lo que el camino delegado no deja hacer desde aqui, y por que. En §21 escribe
# el orquestador y nadie mas; la interfaz no es el orquestador, es un mirador.
SOLO_MIRA = ('el camino delegado lo orquesta una sesion de Claude Code y en su canon'
             ' escribe solo ella. Desde aqui se mira: para actuar, abre Claude Code'
             ' en el repositorio y lanza /orquestar-novela')


class RespuestaError(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _json(valor):
    return json.dumps(valor, ensure_ascii=False).encode('utf-8')


def _texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise RespuestaError(
            400, 'el campo "{}" tiene que ser texto con contenido'.format(campo))
    return valor.strip()


def _entero(valor, campo):
    # Los booleanos de JSON son int en Python y aqui no cuelan como enteros.
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise RespuestaError(400, 'el campo "{}" tiene que ser un entero >= 1'.format(campo))
    return valor


def _cuerpo_json(cuerpo):
    try:
        return json.loads(cuerpo.decode('utf-8')) if cuerpo else {}
    except (ValueError, UnicodeDecodeError):
        raise RespuestaError(400, 'el cuerpo no es JSON valido') from None


def comprobar_brief(bruto):
    """Las mismas cinco claves de §3 que exige la CLI, con la forma minima que el
    canon puede guardar. Los margenes de §12 no se aplican aqui: los vigila VD-07
    sobre la escaleta, que es donde el numero de capitulos significa algo.
    """
    if not isinstance(bruto, dict):
        raise RespuestaError(400, 'el brief tiene que ser un objeto JSON')
    faltan = [c for c in CAMPOS_BRIEF if bruto.get(c) is None]
    if faltan:
        raise RespuestaError(400, 'al brief le falta "{}"'.format('", "'.join(faltan)))
    return {
        'epoca': _texto(bruto['epoca'], 'epoca'),
        'premisa': _texto(bruto['premisa'], 'premisa'),
        'tono': _texto(bruto['tono'], 'tono'),
        'capitulos': _entero(bruto['capitulos'], 'capitulos'),
        'palabras_por_capitulo': _entero(
            bruto['palabras_por_capitulo'], 'palabras_por_capitulo'),
    }


# ------------------------------------------------------------------ perfiles

def perfiles(raiz='.'):
    """Un perfil es uno de los `config*.json` de la raiz.

    Lo que cambia de uno a otro es lo de §12 —modo de ejecucion y modelos—, asi
    que la interfaz no inventa ningun concepto nuevo: ensena los ficheros que
    hay y los que no validan no salen.
    """
    salida = []
    for ruta in sorted(Path(raiz).glob('config*.json')):
        try:
            bruto = cargar_config(str(ruta))
        except ErrorConfig:
            continue
        salida.append({
            'nombre': ruta.stem,
            'ruta': ruta.name,
            'modo': bruto['ejecucion']['modo'],
        })
    return salida


def cargar_perfil(nombre):
    disponibles = {p['nombre']: p['ruta'] for p in perfiles()}
    if nombre not in disponibles:
        raise RespuestaError(400, 'no hay ningun perfil "{}"'.format(nombre))
    return cargar_config(disponibles[nombre])


# --------------------------------------------------------------------- motor

class Motor:
    """El flujo, en un hilo y de uno en uno.

    Guarda el diario que van llenando las funciones de flujo.py —el mismo que
    imprime la CLI— y lo sirve por trozos, para que la pagina cuente lo que
    pasa segun pasa. El estado de verdad sigue viviendo en el canon (§13): si
    el servidor se muere a mitad, esto se pierde y el canon no.
    """

    def __init__(self, config, ruta_canon):
        self.config = config
        self.config_base = config
        self.perfil = None
        self.ruta_canon = ruta_canon
        self.diario = []
        self.accion = None
        self.error = None
        self.detalles = []
        self.arrancado_en = None
        self.terminado_en = None
        self._hilo = None
        self._cerrojo = threading.Lock()

    @property
    def corriendo(self):
        return self._hilo is not None and self._hilo.is_alive()

    def estado(self, desde=0):
        desde = max(0, min(desde, len(self.diario)))
        return {
            'corriendo': self.corriendo,
            'accion': self.accion,
            'perfil': self.perfil,
            'error': self.error,
            'detalles': self.detalles,
            'desde': desde,
            'total': len(self.diario),
            'diario': self.diario[desde:],
            'arrancado_en': self.arrancado_en,
            'terminado_en': self.terminado_en,
        }

    def arrancar(self, accion, perfil=None):
        if accion not in ACCIONES:
            raise RespuestaError(400, 'accion desconocida: {}'.format(accion))
        with self._cerrojo:
            if self.corriendo:
                raise RespuestaError(
                    409, 'ya hay un flujo en marcha ({}); nunca dos a la vez sobre el'
                         ' mismo canon'.format(self.accion))
            self.diario = []
            self.error = None
            self.detalles = []
            self.accion = accion
            self.config = cargar_perfil(perfil) if perfil else self.config_base
            self.perfil = perfil or None
            self.arrancado_en = time.time()
            self.terminado_en = None
            self._hilo = threading.Thread(target=self._correr, args=(accion,), daemon=True)
            self._hilo.start()

    def _anotar(self, rol, vuelta):
        """Lo que cuenta el gancho de Agentes: quien esta trabajando ahora mismo.

        Es el unico evento del diario que no viene de flujo.py, y existe porque
        el resto se anota cuando algo ya ha terminado.
        """
        self.diario.append({'tipo': 'agente', 'rol': rol, 'vuelta': vuelta})

    def _correr(self, accion):
        canon = Canon(self.ruta_canon)
        # El aviso de las trazas entra por el diario, que es lo que la pagina ya
        # lee: si la observabilidad se cae, se ve donde se esta mirando (§20).
        agentes = Agentes(self.config, aviso=lambda m: self.diario.append(
            {'tipo': 'trazas', 'motivo': m}))
        agentes.observador = self._anotar
        if self.config['trazas']['activas'] and not agentes.trazas.activa:
            self.diario.append({'tipo': 'trazas', 'motivo': agentes.trazas.motivo})
        try:
            if accion in ('preparar', 'todo'):
                preparar(canon, agentes, self.config, self.diario)
            if accion in ('escribir', 'todo'):
                self._escribir_hasta_el_final(canon, agentes)
            if accion == 'reanudar':
                reanudar(canon, agentes, self.config, self.diario)
            if accion in ('cerrar', 'todo') and canon.estado() == 'escrito':
                cerrar(canon, agentes, diario=self.diario)
            elif accion == 'cerrar':
                raise ParadaDelProceso(
                    'el editor global corre con el proyecto en escrito, y esta en'
                    ' {}'.format(canon.estado()))
        except ParadaDelProceso as e:
            self.error = e.mensaje
            self.detalles = list(e.detalles)
        except Exception as e:  # el hilo no puede morir en silencio
            self.error = str(e)
        finally:
            # El buzon de trazas se vacia al acabar la pasada y no al morir el
            # servidor: si no, lo ultimo que hizo el flujo no llega nunca.
            agentes.trazas.cerrar()
            canon.cerrar()
            self.terminado_en = time.time()

    def _escribir_hasta_el_final(self, canon, agentes):
        """El mismo bucle que el comando escribir: capitulo a capitulo hasta el
        final o hasta el primer bloqueo. Nunca dos capitulos a la vez, porque el
        N+1 depende del canon que dejo el N (§8).
        """
        siguiente = siguiente_capitulo(canon)
        while siguiente:
            resultado = escribir_capitulo(
                canon, agentes, self.config, siguiente['numero'], self.diario)
            if not resultado['aprobado']:
                return
            siguiente = siguiente_capitulo(canon)
        if not siguiente_capitulo(canon):
            canon.marcar_estado('escrito')


# ------------------------------------------------------------------ lecturas

def _capitulos(canon):
    """La escaleta tal y como la pintan la escena y las tarjetas: un capitulo,
    su estado y, si ya paso el gate, sus tres notas.
    """
    salida = []
    resumenes = {r['capitulo']: r for r in canon.resumenes()}
    for f in canon.fichas():
        intentos = canon.intentos(f['numero'])
        aprobado = next((i for i in intentos if i['estado'] == 'aprobado'), None)
        ns = notas(aprobado['revisiones']) if aprobado and aprobado['revisiones'] else None
        resumen = resumenes.get(f['numero'])
        salida.append({
            'numero': f['numero'],
            'titulo': f['titulo'],
            'acto': f['acto'],
            'sinopsis': f['sinopsis'],
            'estado': f['estado'],
            'palabras_objetivo': f['palabras_objetivo'],
            'palabras': aprobado['palabras'] if aprobado else None,
            'intentos': len(intentos),
            'notas': ns,
            'media': redondear(media(ns), 2) if ns else None,
            'legible': bool(aprobado),
            'resumen': resumen['resumen'] if resumen else None,
        })
    return salida


def _regla_del_intento(intento, config):
    """Que regla decidio este intento.

    No es un dato guardado: se recalcula con el gate de §8 sobre las revisiones
    que si estan en el canon, que es la misma cuenta que se hizo en su momento.
    """
    if not intento['revisiones']:
        return 'VD-08: descartado antes de llamar al validador'
    decision = gate(intento['revisiones'], config['gate'])
    if decision['aprueba']:
        return 'gate: minima {} >= {} y media {} >= {}, sin incidencias graves'.format(
            decision['minima'], config['gate']['nota_minima'],
            numero_corto(redondear(decision['media'], 2)), config['gate']['media_minima'])
    return 'gate: ' + '; '.join(decision['motivos'])


def _intentos(canon, numero, config):
    salida = []
    for i in canon.intentos(numero):
        ns = notas(i['revisiones']) if i['revisiones'] else None
        salida.append({
            'intento': i['intento'],
            # El canon guarda la ruta con el separador del sistema; en la pagina
            # se ensena siempre con barras, como el resto de rutas.
            'ruta': i['ruta'].replace('\\', '/'),
            'palabras': i['palabras'],
            'notas': ns,
            'media': redondear(media(ns), 2) if ns else None,
            'estado': i['estado'],
            'regla': _regla_del_intento(i, config),
            'creado': i['creado'],
        })
    return salida


def _archivos_de_trabajo(tope=8):
    """Lo que el harness ha dejado en disco, del mas reciente al mas antiguo.

    Son los ficheros de verdad: un Markdown por intento (§6) y retoques.md. No
    se lee el canon para esto, se mira la carpeta.
    """
    encontrados = []
    for ruta in list(Path('capitulos').glob('*.md')) + [Path('retoques.md')]:
        if ruta.is_file():
            encontrados.append({
                'ruta': ruta.as_posix(),
                'cuando': ruta.stat().st_mtime,
                'bytes': ruta.stat().st_size,
            })
    encontrados.sort(key=lambda a: a['cuando'], reverse=True)
    return encontrados[:tope]


def _ruta_corta(ruta):
    """La ruta del canon como se escribiria en la consola: relativa si esta bajo
    el directorio de trabajo, y entera solo cuando de verdad esta en otro sitio.
    """
    try:
        return Path(ruta).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return Path(ruta).name


def _proyecto(canon, config, motor=None):
    proyecto = canon.proyecto()
    estado = proyecto['estado'] if proyecto else None
    capitulos = _capitulos(canon) if proyecto else []
    # El capitulo en curso es el que esta en el loop. Si no hay ninguno —lo
    # normal entre pasadas— se ensena el ultimo que tuvo intentos, marcado como
    # no activo: el dato es real y es el que interesa mirar despues.
    en_curso = next((c for c in capitulos if c['estado'] == 'en_curso'), None)
    activo = en_curso is not None
    if en_curso is None:
        en_curso = next((c for c in reversed(capitulos) if c['intentos']), None)
    return {
        'camino': 'harness',
        'orquestador': 'novela/flujo.py',
        'modo': config['ejecucion']['modo'],
        'estado': estado,
        'actualizado': None,
        'brief': {c: proyecto[c] for c in CAMPOS_BRIEF} if proyecto else None,
        'editable': estado in ESTADOS_QUE_ACEPTAN_BRIEF,
        'capitulos': capitulos,
        'gate': config['gate'],
        'margenes': config['margenes'],
        'corriendo': bool(motor and motor.corriendo),
        'retoques': Path('retoques.md').is_file(),
        'canon': _ruta_corta(getattr(motor, 'ruta_canon', 'canon.db')),
        'perfiles': perfiles(),
        'perfil': getattr(motor, 'perfil', None),
        # El capitulo que se esta escribiendo, con sus intentos uno a uno.
        'en_curso': ({'numero': en_curso['numero'], 'titulo': en_curso['titulo'],
                      'activo': activo,
                      'intentos': _intentos(canon, en_curso['numero'], config)}
                     if en_curso else None),
        # Pistas del dossier: id y estado de verificacion (VD-04).
        'dossier': [{'id': d['id'], 'estado': d['estado'], 'categoria': d['categoria']}
                    for d in canon.datos()] if proyecto else [],
        # Deuda narrativa: hilos que un capitulo abrio y ninguno cerro (§7).
        'deuda': canon.hilos_vivos() if proyecto else [],
        # La cronologia de §3 y el reparto de §6, que la pagina pinta igual por
        # los dos caminos porque los dos las guardan.
        'cronologia': canon.eventos() if proyecto else [],
        'reparto': canon.personajes() if proyecto else [],
        # El gate de este camino lo calcula codigo (§8), asi que no hay nada que
        # auditar: la cuenta y la comprobacion serian la misma linea.
        'auditoria': None,
        'archivos': _archivos_de_trabajo(),
        # La cuota diaria no existe en el harness: no hay contabilidad de
        # llamadas ni limite configurado, y aqui no se inventa ninguna de las dos.
        'cuota': None,
    }


def _capitulo(canon, numero):
    """El texto de un capitulo aprobado, con lo que el canon sabe de el.

    Solo aprobados: un intento descartado sigue en capitulos/ como rastro (§6),
    pero no es la novela y no se lee desde aqui.
    """
    ficha = canon.ficha(numero)
    if not ficha:
        raise RespuestaError(404, 'no hay capitulo {}'.format(numero))
    aprobado = canon.intento_aprobado(numero)
    if not aprobado:
        raise RespuestaError(409, 'el capitulo {} todavia no esta aprobado'.format(numero))
    ruta = Path(aprobado['ruta'])
    if not ruta.is_file():
        raise RespuestaError(
            404, 'el canon apunta a {} y ese fichero no esta'.format(aprobado['ruta']))
    resumen = next((r for r in canon.resumenes() if r['capitulo'] == numero), None)
    ns = notas(aprobado['revisiones']) if aprobado['revisiones'] else None
    return {
        'numero': numero,
        'titulo': ficha['titulo'],
        'acto': ficha['acto'],
        'fecha': ficha['fecha'],
        'texto': ruta.read_text(encoding='utf-8'),
        'palabras': aprobado['palabras'],
        'intento': aprobado['intento'],
        'notas': ns,
        'media': redondear(media(ns), 2) if ns else None,
        'revisiones': aprobado['revisiones'],
        'resumen': resumen['resumen'] if resumen else None,
        'hilos_abiertos': resumen['hilos_abiertos'] if resumen else [],
        'hilos_cerrados': resumen['hilos_cerrados'] if resumen else [],
    }


def _desbloquear(canon, datos):
    """Las tres salidas manuales de §8, las mismas que ofrece la CLI."""
    numero = datos.get('capitulo')
    if isinstance(numero, bool) or not isinstance(numero, int):
        raise RespuestaError(400, 'hace falta el numero de capitulo')
    ficha = canon.ficha(numero)
    if not ficha:
        raise RespuestaError(404, 'no hay capitulo {}'.format(numero))
    modo = datos.get('modo') or 'reintentar'

    if modo == 'aprobar':
        intento = datos.get('intento')
        if not any(i['intento'] == intento for i in canon.intentos(numero)):
            raise RespuestaError(
                400, 'el capitulo {} no tiene intento {}'.format(numero, intento))
        canon.fijar_intento_aprobado(numero, intento)
        canon.marcar_ficha(numero, 'aprobado')
        aviso = ('intento {} aprobado a mano: el cronista no ha corrido, asi que el canon'
                 ' no tiene su resumen'.format(intento))
    elif modo == 'reiniciar':
        for i in canon.intentos(numero):
            canon.marcar_intento(numero, i['intento'], 'descartado')
        canon.marcar_ficha(numero, 'pendiente')
        aviso = 'capitulo {} a cero; los intentos quedan como rastro'.format(numero)
    elif modo == 'reintentar':
        canon.marcar_ficha(numero, 'pendiente')
        aviso = 'capitulo {} desbloqueado, el contador de intentos parte de cero'.format(numero)
    else:
        raise RespuestaError(400, 'modo desconocido: {}'.format(modo))

    canon.marcar_estado('escribiendo')
    return {'aviso': aviso}


# ------------------------------------------------- lecturas del camino delegado

# §21 El canon de `novela-cc/` no lo escribe nadie de aqui. Estas funciones lo
# leen y le dan la forma que ya tenia el payload del harness, para que la pagina
# no tenga dos modelos de datos: la sala se pinta igual y lo que cambia es de
# donde salieron las cifras.

def _archivos_cc(canon, tope=8):
    """Lo que el orquestador ha dejado en disco, del mas reciente al mas antiguo.

    Igual que en el harness se mira la carpeta y no el canon, porque la pregunta
    que contesta es "que se ha tocado hace un momento".
    """
    encontrados = []
    raiz = Path(canon.raiz)
    candidatos = (list(raiz.glob('capitulos/*.md'))
                  + list(raiz.glob('contexto/*.md'))
                  + list(raiz.glob('canon/*.json'))
                  + list(raiz.glob('canon/resumenes/*.json'))
                  + [raiz / 'retoques.md'])
    for ruta in candidatos:
        if ruta.is_file():
            encontrados.append({'ruta': ruta.as_posix(),
                                'cuando': ruta.stat().st_mtime,
                                'bytes': ruta.stat().st_size})
    encontrados.sort(key=lambda a: a['cuando'], reverse=True)
    return encontrados[:tope]


def _intentos_cc(canon, numero, config):
    """Los intentos de un capitulo, con la cuenta del gate rehecha encima.

    `regla` no sale del canon: se recalcula con la formula de §8 sobre las notas
    y los graves que si estan guardados, igual que hace el camino del harness.
    Lo que este camino anade es `cuadra`, que dice si esa cuenta coincide con el
    veredicto que el orquestador escribio (§21).
    """
    salida = []
    for i in canon.intentos(numero):
        cuenta = auditar_gate(i, config['gate'])
        salida.append({
            'intento': i.get('intento'),
            'ruta': (i.get('ruta') or '').replace('\\', '/'),
            'palabras': i.get('palabras'),
            'parrafos': i.get('parrafos'),
            'notas': notas_en_lista(i.get('notas')),
            'media': media_de(i.get('notas')),
            'estado': i.get('estado'),
            'regla': operacion(i, config['gate'], cuenta),
            'vd08': i.get('vd08'),
            'motivos': i.get('motivos') or [],
            'avisos': i.get('avisos') or [],
            'tipo_reintento': i.get('tipo_reintento'),
            'cuadra': cuenta['cuadra'] if cuenta else None,
            'creado': None,
        })
    return salida


def _capitulos_cc(canon):
    salida = []
    for ficha in canon.escaleta():
        numero = ficha['numero']
        estado = canon.ficha_estado(numero)
        aprobado = canon.intento_aprobado(numero)
        resumen = canon.resumen(numero)
        salida.append({
            'numero': numero,
            'titulo': ficha.get('titulo'),
            'acto': ficha.get('acto'),
            'sinopsis': ficha.get('sinopsis'),
            'fecha': ficha.get('fecha'),
            'etiquetas': ficha.get('etiquetas') or [],
            'estado': estado['estado'],
            'palabras_objetivo': ficha.get('palabras_objetivo'),
            'palabras': (aprobado or {}).get('palabras'),
            'intentos': len(estado['intentos']),
            'notas': notas_en_lista((aprobado or {}).get('notas')),
            'media': media_de((aprobado or {}).get('notas')),
            'legible': bool(aprobado),
            'resumen': (resumen or {}).get('resumen'),
            # Lo que costo el paquete de §7, que en este camino queda escrito.
            'contexto_tokens': (estado['contexto'] or {}).get('tokens'),
            'recortes': (estado['contexto'] or {}).get('recortes') or [],
        })
    return salida


def _auditoria_cc(canon, config):
    """El resumen de §21: cuantas cuentas del gate cuadran y cuales no.

    Es el unico numero de esta pagina que no describe la novela sino el camino.
    Existe porque §21 dice que la suma del gate la hace un modelo y lo llama su
    punto mas debil; esto es lo que convierte esa frase en algo que se mira.
    """
    revisados = 0
    discrepancias = []
    for ficha in canon.escaleta():
        for i in canon.intentos(ficha['numero']):
            cuenta = auditar_gate(i, config['gate'])
            if not cuenta:
                continue
            revisados += 1
            if not cuenta['cuadra']:
                discrepancias.append({
                    'capitulo': ficha['numero'], 'intento': i.get('intento'),
                    'canon': cuenta['aprueba_canon'], 'formula': cuenta['aprueba'],
                    'operacion': operacion(i, config['gate'], cuenta),
                })
    return {'revisados': revisados, 'discrepancias': discrepancias}


def _proyecto_cc(config, raiz=None):
    canon = CanonCC(raiz) if raiz else CanonCC()
    brief = canon.brief()
    capitulos = _capitulos_cc(canon)
    en_curso = next((c for c in capitulos if c['estado'] == 'en_curso'), None)
    activo = en_curso is not None
    if en_curso is None:
        en_curso = next((c for c in reversed(capitulos) if c['intentos']), None)
    texto_retoques, ruta_retoques = canon.retoques()
    return {
        'camino': 'delegado',
        'orquestador': 'Claude Code',
        # `ejecucion.modo` es del harness (§12) y aqui no significa nada: el
        # modelo lo elige la sesion que orquesta, y el canon no lo guarda.
        'modo': None,
        'estado': canon.estado(),
        'actualizado': canon.actualizado(),
        'brief': brief,
        # Nunca editable: en este canon escribe el orquestador (§21).
        'editable': False,
        'capitulos': capitulos,
        'gate': config['gate'],
        'margenes': config['margenes'],
        'corriendo': False,
        'retoques': bool(texto_retoques),
        'ruta_retoques': ruta_retoques,
        'canon': Path(canon.dir_canon).as_posix(),
        'perfiles': perfiles(),
        'perfil': None,
        'en_curso': ({'numero': en_curso['numero'], 'titulo': en_curso['titulo'],
                      'activo': activo,
                      'intentos': _intentos_cc(canon, en_curso['numero'], config)}
                     if en_curso else None),
        'dossier': [{'id': d.get('id'), 'estado': d.get('estado'),
                     'categoria': d.get('categoria'), 'dato': d.get('dato'),
                     'fuente': d.get('fuente')}
                    for d in canon.datos()],
        'deuda': canon.hilos_vivos(),
        'cronologia': canon.eventos(),
        'reparto': canon.personajes(),
        'auditoria': _auditoria_cc(canon, config),
        'archivos': _archivos_cc(canon),
        # Igual que en el harness: no hay contabilidad de llamadas ni limite.
        'cuota': None,
    }


def _capitulo_cc(config, numero, raiz=None):
    canon = CanonCC(raiz) if raiz else CanonCC()
    ficha = next((c for c in canon.escaleta() if c['numero'] == numero), None)
    if not ficha:
        raise RespuestaError(404, 'no hay capitulo {}'.format(numero))
    aprobado = canon.intento_aprobado(numero)
    if not aprobado:
        raise RespuestaError(409, 'el capitulo {} todavia no esta aprobado'.format(numero))
    texto, ruta = canon.texto(numero)
    if texto is None:
        raise RespuestaError(404, 'el canon apunta a {} y ese fichero no esta'.format(ruta))
    resumen = canon.resumen(numero) or {}
    return {
        'numero': numero,
        'titulo': ficha.get('titulo'),
        'acto': ficha.get('acto'),
        'fecha': ficha.get('fecha'),
        'texto': texto,
        'ruta': ruta,
        'palabras': aprobado.get('palabras'),
        'parrafos': aprobado.get('parrafos'),
        'intento': aprobado.get('intento'),
        'notas': notas_en_lista(aprobado.get('notas')),
        'media': media_de(aprobado.get('notas')),
        # El canon delegado guarda la nota y el aviso, no el bloque entero de
        # revision: no hay citas ni sugerencias, y no se inventan.
        'revisiones': [],
        'avisos': aprobado.get('avisos') or [],
        'resumen': resumen.get('resumen'),
        'hilos_abiertos': resumen.get('hilos_abiertos') or [],
        'hilos_cerrados': resumen.get('hilos_cerrados') or [],
        'personajes_presentes': resumen.get('personajes_presentes') or [],
    }


# -------------------------------------------------------- paquete de contexto

def _contexto(via, canon, config, numero):
    """El paquete con el que se escribio un capitulo (§7).

    En el camino delegado esta en disco -el orquestador lo escribe ahi justo
    para esto- y en el del harness se regenera con el canon de ahora mismo. Son
    dos cosas distintas y la respuesta lo dice, porque regenerado no es el que
    vio el escritor: el canon ha cambiado desde entonces.
    """
    if via == 'delegado':
        texto, ruta = CanonCC().contexto(numero)
        if texto is None:
            raise RespuestaError(404, 'no hay paquete guardado en {}'.format(ruta))
        return {'capitulo': numero, 'texto': texto, 'ruta': ruta,
                'origen': 'guardado', 'tokens': None, 'recortes': []}
    if not canon.ficha(numero):
        raise RespuestaError(404, 'no hay capitulo {}'.format(numero))
    paquete = generar_contexto(canon, numero, config)
    return {'capitulo': numero, 'texto': paquete['texto'], 'ruta': None,
            'origen': 'regenerado', 'tokens': paquete['tokens'],
            'recortes': paquete['recortes']}


# -------------------------------------------------------------- trazas (§20)

# Lo ultimo que se mando, para que la pagina pueda decir "esto ya salio" sin
# volver a mandarlo. Es del proceso y no del canon: si el servidor se muere se
# pierde, y da igual, porque la verdad de esto vive en Langfuse.
_ULTIMO_ENVIO = {}


def _trazas(via, config):
    disponible = trazas_cc.disponibilidad(config)
    salida = {
        'camino': via,
        'activas': bool(config['trazas']['activas']),
        'entorno': config['trazas']['entorno'],
        'lista': disponible['lista'],
        'motivo': disponible['motivo'],
        'ultimo': _ULTIMO_ENVIO.get(via),
        'plan': None,
        # En el harness las trazas salen solas con cada llamada (§20); aqui no
        # hay llamada que interceptar y se reconstruyen desde el canon (§21).
        'reconstruido': via == 'delegado',
    }
    if via == 'delegado':
        canon = CanonCC()
        salida['plan'] = trazas_cc.plan(canon, config) if canon.existe else None
    return salida


def _exportar_trazas(via, config):
    if via != 'delegado':
        raise RespuestaError(
            409, 'el harness traza mientras corre; aqui no hay nada que reconstruir')
    resultado = trazas_cc.exportar(config)
    _ULTIMO_ENVIO[via] = {
        'cuando': time.time(),
        'enviado': resultado['enviado'],
        'motivo': resultado.get('motivo'),
        'trazas': resultado.get('trazas'),
        'sesion': resultado.get('sesion'),
    }
    return resultado


# ----------------------------------------------------------------- enrutado

def _estatico(camino, raiz_web):
    raiz = Path(raiz_web).resolve()
    destino = (raiz / camino.lstrip('/')).resolve() if camino.strip('/') else raiz / 'index.html'
    try:
        destino.relative_to(raiz)
    except ValueError:
        # Un ../ que se sale de web/: fuera de ese arbol no hay nada que servir.
        raise RespuestaError(404, 'no existe {}'.format(camino)) from None
    if not destino.is_file():
        raise RespuestaError(404, 'no existe {}'.format(camino))
    return 200, TIPOS.get(destino.suffix.lower(), 'application/octet-stream'), \
        destino.read_bytes()


def _via(parametros, config):
    """Por cual de los dos caminos mira esta peticion.

    Lo pide la pagina en cada llamada y el perfil pone el valor de partida
    (§12). Un camino que no existe se rechaza en vez de caer al de por defecto:
    ensenar el canon equivocado sin decirlo es peor que un 400.
    """
    pedido = parametros.get('camino', [None])[0]
    if pedido is None:
        return (config.get('interfaz') or {}).get('camino') or 'harness'
    if pedido not in CAMINOS:
        raise RespuestaError(400, 'camino desconocido: {}'.format(pedido))
    return pedido


def responder(metodo, camino, cuerpo, canon, config, motor=None, raiz_web=RAIZ_WEB):
    """Enrutado entero, sin socket de por medio: el manejador HTTP solo traduce.

    Devuelve (codigo, tipo de contenido, bytes).
    """
    camino, _, consulta = camino.partition('?')
    parametros = parse_qs(consulta)
    try:
        via = _via(parametros, config) if camino.startswith('/api/') else 'harness'

        if camino == '/api/proyecto' and metodo == 'GET':
            if via == 'delegado':
                return 200, TIPOS['.json'], _json(_proyecto_cc(config))
            return 200, TIPOS['.json'], _json(_proyecto(canon, config, motor))

        if camino == '/api/brief' and metodo == 'POST':
            if via == 'delegado':
                raise RespuestaError(409, SOLO_MIRA)
            estado = canon.estado()
            if estado not in ESTADOS_QUE_ACEPTAN_BRIEF:
                raise RespuestaError(
                    409, 'el proyecto esta en "{}" y la interfaz no pisa un libro en'
                         ' marcha; para rehacer el brief usa "python -m novela'
                         ' brief"'.format(estado))
            canon.guardar_brief(comprobar_brief(_cuerpo_json(cuerpo)))
            return 200, TIPOS['.json'], _json(_proyecto(canon, config, motor))

        if camino == '/api/flujo':
            if via == 'delegado':
                if metodo == 'POST':
                    raise RespuestaError(409, SOLO_MIRA)
                # El diario de §19 lo llena el motor del harness. En el camino
                # delegado el relato esta en la conversacion de Claude Code, no
                # aqui: se devuelve vacio y la pagina lo dice, en vez de fingir
                # un stream que nadie esta escribiendo.
                return 200, TIPOS['.json'], _json({
                    'corriendo': False, 'accion': None, 'perfil': None,
                    'error': None, 'detalles': [], 'desde': 0, 'total': 0,
                    'diario': [], 'arrancado_en': None, 'terminado_en': None,
                    'sin_motor': True})
            if not motor:
                raise RespuestaError(503, 'esta interfaz no tiene motor de flujo')
            if metodo == 'GET':
                desde = parametros.get('desde', ['0'])[0]
                return 200, TIPOS['.json'], _json(
                    motor.estado(int(desde) if desde.isdigit() else 0))
            if metodo == 'POST':
                peticion = _cuerpo_json(cuerpo) or {}
                motor.arrancar(peticion.get('accion'), peticion.get('perfil'))
                return 202, TIPOS['.json'], _json(motor.estado())

        if camino == '/api/desbloquear' and metodo == 'POST':
            if via == 'delegado':
                raise RespuestaError(409, SOLO_MIRA)
            if motor and motor.corriendo:
                raise RespuestaError(
                    409, 'hay un flujo en marcha; para y vuelve a intentarlo')
            return 200, TIPOS['.json'], _json(_desbloquear(canon, _cuerpo_json(cuerpo)))

        if camino == '/api/trazas':
            if metodo == 'GET':
                return 200, TIPOS['.json'], _json(_trazas(via, config))
            if metodo == 'POST':
                return 200, TIPOS['.json'], _json(_exportar_trazas(via, config))

        if camino.startswith('/api/capitulo/') and metodo == 'GET':
            resto = camino[len('/api/capitulo/'):]
            if not resto.isdigit():
                raise RespuestaError(400, 'el capitulo se pide por numero')
            if via == 'delegado':
                return 200, TIPOS['.json'], _json(_capitulo_cc(config, int(resto)))
            return 200, TIPOS['.json'], _json(_capitulo(canon, int(resto)))

        if camino.startswith('/api/contexto/') and metodo == 'GET':
            resto = camino[len('/api/contexto/'):]
            if not resto.isdigit():
                raise RespuestaError(400, 'el contexto se pide por numero de capitulo')
            return 200, TIPOS['.json'], _json(
                _contexto(via, canon, config, int(resto)))

        if camino.startswith('/api/'):
            raise RespuestaError(404, 'no existe {} {}'.format(metodo, camino))

        if metodo != 'GET':
            raise RespuestaError(405, '{} no vale aqui'.format(metodo))
        return _estatico(camino, raiz_web)

    except RespuestaError as e:
        return e.codigo, TIPOS['.json'], _json({'error': e.mensaje})


class Manejador(BaseHTTPRequestHandler):
    """Traductor entre el socket y responder(). Todo lo que decide vive arriba."""

    config = None
    ruta_canon = 'canon.db'
    raiz_web = RAIZ_WEB
    motor = None

    def _servir(self, metodo):
        longitud = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(longitud) if longitud else b''
        # Un canon por peticion: el flujo escribe desde el hilo del motor y la
        # interfaz solo lee lo que ya esta escrito.
        canon = Canon(self.ruta_canon)
        try:
            codigo, tipo, datos = responder(
                metodo, self.path, cuerpo, canon, self.config, self.motor, self.raiz_web)
        finally:
            canon.cerrar()
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(datos)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        self._servir('GET')

    def do_POST(self):
        self._servir('POST')

    def log_message(self, formato, *args):
        pass  # El diario del harness es el de §4; el ruido de HTTP no pinta nada.


def crear_servidor(config, ruta_canon, puerto=None, raiz_web=RAIZ_WEB):
    clase = type('ManejadorConfigurado', (Manejador,), {
        'config': config,
        'ruta_canon': ruta_canon,
        'raiz_web': Path(raiz_web),
        'motor': Motor(config, ruta_canon),
    })
    # Solo 127.0.0.1: la interfaz es local, de un solo usuario y sin nada que
    # autenticar. Un hilo para las peticiones y otro para el flujo, y nunca dos
    # flujos a la vez, que es lo que pide §8.
    puerto = puerto if puerto is not None else config['interfaz']['puerto']
    return HTTPServer(('127.0.0.1', puerto), clase)


def arrancar(config, ruta_canon, puerto=None, abrir=True, log=print):
    servidor = crear_servidor(config, ruta_canon, puerto)
    url = 'http://127.0.0.1:{}/'.format(servidor.server_address[1])
    log('interfaz en {}   (canon: {}, modo: {})'.format(
        url, ruta_canon, config['ejecucion']['modo']))
    log('Desde ahi se escribe el brief y se lanza el flujo. Ctrl+C para parar.')
    if abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log('')
    finally:
        servidor.server_close()
    return 0
