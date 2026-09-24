# §19 Interfaz web. Servidor local de la biblioteca estandar: sirve web/ y
# expone una API pequena sobre el canon de las novelas de la biblioteca (§21).
# Sin `?novela=` se mira la novela en curso; con el, cualquiera de las demas.
#
# **En el canon escribe el orquestador y nadie mas** (§21). Aqui no hay motor ni
# hilo de flujo, y ninguna ruta toca un fichero del canon: lo que hay es un
# mirador sobre lo que la sesion de Claude Code va dejando escrito.
#
# La unica excepcion al «solo GET» es POST /api/lanzar, y no rompe esa regla:
# arranca al orquestador con el brief que se ha tecleado y se aparta. Quien
# escribe la novela sigue siendo el, no esto.
#
# Ningun dato de esta pantalla es propio de la interfaz: o se lee del canon o se
# recalcula con las reglas del spec. Lo que el canon no guarda se dice que no
# esta, y no se rellena.
import json
import time
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from . import biblioteca, lanzador, trazas_cc
from .config import cargar_config, ErrorConfig
from .canon_cc import CanonCC, auditar_gate, media_de, notas_en_lista, operacion

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

# Lo que no se puede hacer desde aqui, y por que. Sale en la respuesta de
# cualquier metodo que no sea GET contra la API, salvo las dos rutas que no
# tocan el canon: la de trazas y la de lanzar.
SOLO_MIRA = ('en este canon escribe la sesion de Claude Code que orquesta, y nadie'
             ' mas (§21). Desde aqui se mira: para actuar, abre Claude Code en el'
             ' repositorio y lanza /orquestar-novela')


class RespuestaError(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _json(valor):
    return json.dumps(valor, ensure_ascii=False).encode('utf-8')


# ------------------------------------------------------------------ perfiles

def perfiles(raiz='.'):
    """Un perfil es uno de los `config*.json` de la raiz, nada mas.

    Lo que cambia de uno a otro son los umbrales de §12, asi que la interfaz no
    inventa ningun concepto nuevo: ensena los ficheros que hay y los que no
    validan no salen.
    """
    salida = []
    for ruta in sorted(Path(raiz).glob('config*.json')):
        try:
            cargar_config(str(ruta))
        except ErrorConfig:
            continue
        salida.append({'nombre': ruta.stem, 'ruta': ruta.name})
    return salida


# ------------------------------------------------------------------ lecturas

def _archivos(canon, tope=8):
    """Lo que el orquestador ha dejado en disco, del mas reciente al mas antiguo.

    Se mira la carpeta y no el canon, porque la pregunta que contesta es "que se
    ha tocado hace un momento".
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


def _intentos(canon, numero, config):
    """Los intentos de un capitulo, con la cuenta del gate rehecha encima.

    `regla` no sale del canon: se recalcula con la formula de §8 sobre las notas
    y los graves que si estan guardados. `cuadra` dice si esa cuenta coincide
    con el veredicto que el orquestador escribio, que es lo unico que se puede
    hacer cuando la suma la hace un modelo (DA-15).
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


def _capitulos(canon):
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
            # Lo que costo el paquete de §7, que el orquestador deja escrito.
            'contexto_tokens': (estado['contexto'] or {}).get('tokens'),
            'recortes': (estado['contexto'] or {}).get('recortes') or [],
        })
    return salida


def _auditoria(canon, config):
    """Cuantas cuentas del gate cuadran y cuales no.

    Es el unico numero de esta pagina que no describe la novela sino el sistema.
    Existe porque el gate dejo de ser codigo: la formula esta escrita y la suma
    la hace un modelo, y esto es lo que convierte esa frase en algo que se mira.
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


def _proyecto(config, raiz=None):
    canon = CanonCC(raiz) if raiz else CanonCC()
    # La carpeta de la novela, que es su nombre en la biblioteca y en la URL de
    # la pagina. Existe aunque aun no tenga canon: el lanzador la aparta antes
    # de que el orquestador escriba nada. Sin ninguna, no hay novela que nombrar.
    carpeta = raiz or biblioteca.actual()
    capitulos = _capitulos(canon)
    # El capitulo en curso es el que esta en el loop. Si no hay ninguno -lo
    # normal entre pasadas- se ensena el ultimo que tuvo intentos, marcado como
    # no activo: el dato es real y es el que interesa mirar despues.
    en_curso = next((c for c in capitulos if c['estado'] == 'en_curso'), None)
    activo = en_curso is not None
    if en_curso is None:
        en_curso = next((c for c in reversed(capitulos) if c['intentos']), None)
    texto_retoques, ruta_retoques = canon.retoques()
    return {
        'orquestador': 'Claude Code',
        'novela': Path(carpeta).name if carpeta else None,
        'estado': canon.estado(),
        'actualizado': canon.actualizado(),
        'brief': canon.brief(),
        'capitulos': capitulos,
        'gate': config['gate'],
        'margenes': config['margenes'],
        'retoques': bool(texto_retoques),
        'ruta_retoques': ruta_retoques,
        'canon': Path(canon.dir_canon).as_posix(),
        'perfiles': perfiles(),
        'en_curso': ({'numero': en_curso['numero'], 'titulo': en_curso['titulo'],
                      'activo': activo,
                      'intentos': _intentos(canon, en_curso['numero'], config)}
                     if en_curso else None),
        'dossier': [{'id': d.get('id'), 'estado': d.get('estado'),
                     'categoria': d.get('categoria'), 'dato': d.get('dato'),
                     'fuente': d.get('fuente')}
                    for d in canon.datos()],
        'deuda': canon.hilos_vivos(),
        'cronologia': canon.eventos(),
        'reparto': canon.personajes(),
        'auditoria': _auditoria(canon, config),
        'archivos': _archivos(canon),
        # No hay contabilidad de llamadas ni limite configurado, y aqui no se
        # inventa ninguna de las dos: se dice que no hay dato.
        'cuota': None,
    }


def _capitulo(config, numero, raiz=None):
    """El texto de un capitulo aprobado, con lo que el canon sabe de el.

    Solo aprobados: un intento descartado sigue en capitulos/ como rastro, pero
    no es la novela y no se lee desde aqui.
    """
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
        # El canon guarda la nota y el aviso, no el bloque entero de revision:
        # no hay citas ni sugerencias, y no se inventan.
        'revisiones': [],
        'avisos': aprobado.get('avisos') or [],
        'resumen': resumen.get('resumen'),
        'hilos_abiertos': resumen.get('hilos_abiertos') or [],
        'hilos_cerrados': resumen.get('hilos_cerrados') or [],
        'personajes_presentes': resumen.get('personajes_presentes') or [],
    }


def _contexto(numero, raiz=None):
    """El paquete con el que se escribio un capitulo (§7).

    Esta en disco: el orquestador lo escribe ahi justo para esto, y por eso es
    el paquete que de verdad vio el escritor y no una reconstruccion con el
    canon de ahora, que ya ha cambiado.
    """
    canon = CanonCC(raiz) if raiz else CanonCC()
    texto, ruta = canon.contexto(numero)
    if texto is None:
        raise RespuestaError(404, 'no hay paquete guardado en {}'.format(ruta))
    return {'capitulo': numero, 'texto': texto, 'ruta': ruta, 'origen': 'guardado'}


# ---------------------------------------------------------------- biblioteca

def _carpeta(consulta):
    """La carpeta que pide `?novela=`, o None para la novela en curso.

    El nombre se busca entre las carpetas que hay y no se compone con el: un
    `../config` no es una novela, y asi no hace falta limpiarlo para que no se
    salga de `biblioteca/`.
    """
    nombre = (parse_qs(consulta).get('novela') or [''])[0].strip()
    if not nombre:
        return None
    for carpeta in biblioteca.carpetas():
        if carpeta.name == nombre:
            return carpeta.as_posix()
    raise RespuestaError(404, 'no hay ninguna novela que se llame {} en {}/'.format(
        nombre, biblioteca.RAIZ))


def _novelas(config):
    """Las novelas de la biblioteca, cada una con lo que su tarjeta ensena.

    Es el tablero del taller: una fila por carpeta, con su estado de §4 y los
    recuentos de su escaleta. Todo sale del canon de cada una o se recalcula
    con las reglas del spec; lo que una carpeta aun no tiene va vacio y no se
    rellena con lo que pidio el brief.
    """
    lanzado = lanzador.estado()
    con_sesion = (lanzado.get('lanzado') or {}).get('novela') if lanzado.get('corriendo') else None
    actual = biblioteca.actual()
    salida = []
    for novela in biblioteca.listar():
        canon = CanonCC(novela['ruta'])
        capitulos = _capitulos(canon)
        cuenta = Counter(c['estado'] for c in capitulos)
        texto_retoques, _ = canon.retoques()
        salida.append({
            'nombre': novela['nombre'],
            'ruta': novela['ruta'],
            'cuando': novela['cuando'],
            'actual': novela['ruta'] == actual,
            # Solo la sesion que se arranco desde aqui: una abierta a mano en
            # Claude Code no deja rastro que esta pagina pueda ver.
            'sesion': novela['nombre'] == con_sesion,
            'estado': canon.estado(),
            'actualizado': canon.actualizado(),
            'brief': canon.brief(),
            'capitulos': {
                'total': len(capitulos),
                'aprobados': cuenta['aprobado'],
                'en_curso': cuenta['en_curso'],
                'bloqueados': cuenta['bloqueado'],
            },
            'intentos': sum(c['intentos'] for c in capitulos),
            'discrepancias': len(_auditoria(canon, config)['discrepancias']),
            'retoques': bool(texto_retoques),
        })
    return {'novelas': salida, 'raiz': biblioteca.RAIZ}


# -------------------------------------------------------------- trazas (§20)

# Lo ultimo que se mando de cada novela, para que la pagina pueda decir "esto
# ya salio" sin volver a mandarlo. Es del proceso y no del canon: si el servidor
# se muere se pierde, y da igual, porque la verdad de esto vive en Langfuse.
_ULTIMO_ENVIO = {}


def _trazas(config, raiz=None):
    disponible = trazas_cc.disponibilidad(config)
    canon = CanonCC(raiz) if raiz else CanonCC()
    return {
        'activas': bool(config['trazas']['activas']),
        'entorno': config['trazas']['entorno'],
        'lista': disponible['lista'],
        'motivo': disponible['motivo'],
        'ultimo': _ULTIMO_ENVIO.get(Path(canon.raiz).name),
        'plan': trazas_cc.plan(canon, config) if canon.existe else None,
        # Lo que sale de aqui se reconstruye del canon: sin latencia, sin tokens
        # y sin coste. Lo que si los tiene lo manda el hook de §22 en vivo.
        'reconstruido': True,
    }


def _exportar_trazas(config, raiz=None):
    resultado = trazas_cc.exportar(config, raiz)
    _ULTIMO_ENVIO[Path(raiz or CanonCC().raiz).name] = {
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


def responder(metodo, camino, cuerpo, config, raiz_web=RAIZ_WEB):
    """Enrutado entero, sin socket de por medio: el manejador HTTP solo traduce.

    Devuelve (codigo, tipo de contenido, bytes).
    """
    camino, _, consulta = camino.partition('?')
    try:
        if camino == '/api/novelas' and metodo == 'GET':
            return 200, TIPOS['.json'], _json(_novelas(config))

        if camino == '/api/proyecto' and metodo == 'GET':
            return 200, TIPOS['.json'], _json(_proyecto(config, _carpeta(consulta)))

        if camino == '/api/trazas':
            if metodo == 'GET':
                return 200, TIPOS['.json'], _json(_trazas(config, _carpeta(consulta)))
            if metodo == 'POST':
                # La unica escritura que hace esta interfaz sale del repositorio
                # entero: manda a Langfuse lo que el canon ya dice. No toca el
                # canon, que es lo que SOLO_MIRA protege.
                return 200, TIPOS['.json'], _json(
                    _exportar_trazas(config, _carpeta(consulta)))

        if camino == '/api/lanzar':
            # La otra ruta que no es GET y tampoco escribe en el canon: arranca
            # una sesion de Claude Code con el brief y se aparta. Quien escribe
            # la novela es esa sesion, igual que si se hubiera abierto a mano.
            if metodo == 'GET':
                return 200, TIPOS['.json'], _json(lanzador.estado())
            if metodo == 'POST':
                try:
                    peticion = json.loads(cuerpo or b'{}')
                except ValueError:
                    raise RespuestaError(400, 'el cuerpo no es JSON') from None
                try:
                    return 200, TIPOS['.json'], _json(lanzador.lanzar(peticion, config))
                except lanzador.ErrorLanzador as e:
                    raise RespuestaError(409, str(e)) from None

        if camino.startswith('/api/capitulo/') and metodo == 'GET':
            resto = camino[len('/api/capitulo/'):]
            if not resto.isdigit():
                raise RespuestaError(400, 'el capitulo se pide por numero')
            return 200, TIPOS['.json'], _json(
                _capitulo(config, int(resto), _carpeta(consulta)))

        if camino.startswith('/api/contexto/') and metodo == 'GET':
            resto = camino[len('/api/contexto/'):]
            if not resto.isdigit():
                raise RespuestaError(400, 'el contexto se pide por numero de capitulo')
            return 200, TIPOS['.json'], _json(_contexto(int(resto), _carpeta(consulta)))

        if camino.startswith('/api/'):
            if metodo != 'GET':
                raise RespuestaError(409, SOLO_MIRA)
            raise RespuestaError(404, 'no existe {} {}'.format(metodo, camino))

        if metodo != 'GET':
            raise RespuestaError(405, '{} no vale aqui'.format(metodo))
        return _estatico(camino, raiz_web)

    except RespuestaError as e:
        return e.codigo, TIPOS['.json'], _json({'error': e.mensaje})


class Manejador(BaseHTTPRequestHandler):
    """Traductor entre el socket y responder(). Todo lo que decide vive arriba."""

    config = None
    raiz_web = RAIZ_WEB

    def _servir(self, metodo):
        longitud = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(longitud) if longitud else b''
        codigo, tipo, datos = responder(
            metodo, self.path, cuerpo, self.config, self.raiz_web)
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
        pass  # El relato de lo que pasa esta en Claude Code; el ruido de HTTP no.


def crear_servidor(config, puerto=None, raiz_web=RAIZ_WEB):
    clase = type('ManejadorConfigurado', (Manejador,), {
        'config': config,
        'raiz_web': Path(raiz_web),
    })
    # Solo 127.0.0.1: la interfaz es local, de un solo usuario y sin nada que
    # autenticar.
    puerto = puerto if puerto is not None else config['interfaz']['puerto']
    return HTTPServer(('127.0.0.1', puerto), clase)


def arrancar(config, puerto=None, abrir=True, log=print):
    servidor = crear_servidor(config, puerto)
    url = 'http://127.0.0.1:{}/'.format(servidor.server_address[1])
    canon = CanonCC()
    log('interfaz en {}   (canon: {})'.format(url, Path(canon.dir_canon).as_posix()))
    log('Mira el canon y no escribe en el. Para escribir la novela, /orquestar-novela'
        ' en Claude Code. Ctrl+C para parar.')
    if abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log('')
    finally:
        servidor.server_close()
    return 0
