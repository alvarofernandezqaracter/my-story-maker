# §19 Interfaz web del brief. Servidor local de la biblioteca estandar: sirve
# web/ y expone una API minuscula sobre el canon. No decide nada del sistema,
# igual que la CLI (§18): valida la forma del brief, llama al canon y devuelve
# JSON. Ningun endpoint lanza agentes ni escribe fuera de la fila de proyecto.
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .canon import Canon
from .gate import media, notas
from .util import redondear

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
# dejaria el canon hablando de otra novela, asi que la interfaz no lo permite y
# remite a la CLI, que si deja hacerlo a sabiendas.
ESTADOS_QUE_ACEPTAN_BRIEF = (None, 'borrador')


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


def _capitulos(canon):
    """La escaleta tal y como la pinta la escena: un capitulo, su estado y, si ya
    paso el gate, sus tres notas.
    """
    salida = []
    for f in canon.fichas():
        aprobado = canon.intento_aprobado(f['numero'])
        ns = notas(aprobado['revisiones']) if aprobado and aprobado['revisiones'] else None
        salida.append({
            'numero': f['numero'],
            'titulo': f['titulo'],
            'estado': f['estado'],
            'palabras_objetivo': f['palabras_objetivo'],
            'intentos': len(canon.intentos(f['numero'])),
            'notas': ns,
            'media': redondear(media(ns), 2) if ns else None,
        })
    return salida


def _proyecto(canon, config):
    proyecto = canon.proyecto()
    estado = proyecto['estado'] if proyecto else None
    return {
        'modo': config['ejecucion']['modo'],
        'estado': estado,
        'brief': {c: proyecto[c] for c in CAMPOS_BRIEF} if proyecto else None,
        'editable': estado in ESTADOS_QUE_ACEPTAN_BRIEF,
        'capitulos': _capitulos(canon) if proyecto else [],
    }


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


def responder(metodo, camino, cuerpo, canon, config, raiz_web=RAIZ_WEB):
    """Enrutado entero, sin socket de por medio: el manejador HTTP solo traduce.

    Devuelve (codigo, tipo de contenido, bytes).
    """
    try:
        if camino == '/api/proyecto' and metodo == 'GET':
            return 200, TIPOS['.json'], _json(_proyecto(canon, config))

        if camino == '/api/brief' and metodo == 'POST':
            estado = canon.estado()
            if estado not in ESTADOS_QUE_ACEPTAN_BRIEF:
                raise RespuestaError(
                    409, 'el proyecto esta en "{}" y la interfaz no pisa un libro en'
                         ' marcha; para rehacer el brief usa "python -m novela'
                         ' brief"'.format(estado))
            try:
                bruto = json.loads(cuerpo.decode('utf-8')) if cuerpo else None
            except (ValueError, UnicodeDecodeError):
                raise RespuestaError(400, 'el cuerpo no es JSON valido') from None
            canon.guardar_brief(comprobar_brief(bruto))
            return 200, TIPOS['.json'], _json(_proyecto(canon, config))

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

    def _servir(self, metodo):
        camino = self.path.split('?')[0]
        longitud = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(longitud) if longitud else b''
        # Un canon por peticion: el flujo puede estar corriendo en otra consola
        # sobre el mismo fichero, y la interfaz solo lee lo que ya esta escrito.
        canon = Canon(self.ruta_canon)
        try:
            codigo, tipo, datos = responder(
                metodo, camino, cuerpo, canon, self.config, self.raiz_web)
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
    })
    # Solo 127.0.0.1: la interfaz es local, de un solo usuario y sin nada que
    # autenticar. Un servidor de un hilo basta y ademas respeta el invariante de
    # §8: dentro del harness no corre nada en paralelo.
    puerto = puerto if puerto is not None else config['interfaz']['puerto']
    return HTTPServer(('127.0.0.1', puerto), clase)


def arrancar(config, ruta_canon, puerto=None, abrir=True, log=print):
    servidor = crear_servidor(config, ruta_canon, puerto)
    url = 'http://127.0.0.1:{}/'.format(servidor.server_address[1])
    log('interfaz en {}   (canon: {}, modo: {})'.format(
        url, ruta_canon, config['ejecucion']['modo']))
    log('La interfaz escribe el brief y nada mas: el flujo sigue en la CLI con')
    log('"python -m novela preparar". Ctrl+C para parar.')
    if abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log('')
    finally:
        servidor.server_close()
    return 0
