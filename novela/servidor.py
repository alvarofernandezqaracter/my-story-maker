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

from .agentes import Agentes, ParadaDelProceso
from .config import cargar_config, ErrorConfig
from .canon import Canon
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
        agentes = Agentes(self.config)
        agentes.observador = self._anotar
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
        'modo': config['ejecucion']['modo'],
        'estado': estado,
        'brief': {c: proyecto[c] for c in CAMPOS_BRIEF} if proyecto else None,
        'editable': estado in ESTADOS_QUE_ACEPTAN_BRIEF,
        'capitulos': capitulos,
        'gate': config['gate'],
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


def responder(metodo, camino, cuerpo, canon, config, motor=None, raiz_web=RAIZ_WEB):
    """Enrutado entero, sin socket de por medio: el manejador HTTP solo traduce.

    Devuelve (codigo, tipo de contenido, bytes).
    """
    camino, _, consulta = camino.partition('?')
    parametros = parse_qs(consulta)
    try:
        if camino == '/api/proyecto' and metodo == 'GET':
            return 200, TIPOS['.json'], _json(_proyecto(canon, config, motor))

        if camino == '/api/brief' and metodo == 'POST':
            estado = canon.estado()
            if estado not in ESTADOS_QUE_ACEPTAN_BRIEF:
                raise RespuestaError(
                    409, 'el proyecto esta en "{}" y la interfaz no pisa un libro en'
                         ' marcha; para rehacer el brief usa "python -m novela'
                         ' brief"'.format(estado))
            canon.guardar_brief(comprobar_brief(_cuerpo_json(cuerpo)))
            return 200, TIPOS['.json'], _json(_proyecto(canon, config, motor))

        if camino == '/api/flujo':
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
            if motor and motor.corriendo:
                raise RespuestaError(
                    409, 'hay un flujo en marcha; para y vuelve a intentarlo')
            return 200, TIPOS['.json'], _json(_desbloquear(canon, _cuerpo_json(cuerpo)))

        if camino.startswith('/api/capitulo/') and metodo == 'GET':
            resto = camino[len('/api/capitulo/'):]
            if not resto.isdigit():
                raise RespuestaError(400, 'el capitulo se pide por numero')
            return 200, TIPOS['.json'], _json(_capitulo(canon, int(resto)))

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
