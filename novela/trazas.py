# §20 Observabilidad. Capa unica de trazas contra Langfuse, con la misma regla
# que la capa de agentes de §5: de aqui hacia arriba nadie sabe si hay trazas.
# Cuando estan apagadas, o cuando falta el SDK o la credencial, todo lo de este
# fichero devuelve objetos mudos y todo lo demas corre exactamente igual.
#
# Las trazas NO son fuente de verdad de nada. El estado vive en el canon (§13),
# el gate decide en codigo (§8) y lo de aqui solo observa. Si Langfuse no
# responde, la novela se escribe igual: por eso todo va envuelto en captura de
# excepciones y ningun fallo de observabilidad puede parar el proceso.
import hashlib
import json
import os
import re
from contextlib import contextmanager, ExitStack

from . import __version__
from .entorno import cargar_entorno

# Las credenciales de §20. No van en config.json porque ese fichero se versiona.
CLAVES = ('LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY')

# Lo que parece una credencial no entra en una traza aunque se cuele en un
# prompt. No es teorico: las instrucciones de §10 son texto libre y el brief lo
# escribe una persona.
CREDENCIALES = re.compile(
    r'\b(?:sk|pk)-[A-Za-z0-9_\-]{8,}|\bBearer\s+[A-Za-z0-9._\-]{16,}', re.IGNORECASE)

TAPADO = '[CREDENCIAL_OCULTA]'

# Nombre de la generacion de cada rol (§20). Verbo delante y sin el numero de
# capitulo dentro: el nombre identifica la operacion, no una ejecucion suya, y
# si lleva el numero deja de poder agruparse.
GENERACIONES = {
    'investigador': 'investigar-epoca',
    'arquitecto': 'disenar-escaleta',
    'escritor': 'redactar-capitulo',
    'validador': 'revisar-capitulo',
    'cronista': 'resumir-capitulo',
    'editor_global': 'proponer-retoques',
}


def enmascarar(*, data, **_):
    """Mask de Langfuse: corre sobre cada entrada y salida antes de salir."""
    try:
        crudo = data if isinstance(data, str) else json.dumps(
            data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return data
    if not CREDENCIALES.search(crudo):
        return data
    limpio = CREDENCIALES.sub(TAPADO, crudo)
    if isinstance(data, str):
        return limpio
    try:
        return json.loads(limpio)
    except ValueError:
        return limpio


def reparto_de_tokens(bruto):
    """Traduce el gasto de una llamada al reparto que espera Langfuse (§20).

    Las cubetas no se solapan: `input_tokens` de Anthropic ya viene sin lo que
    se leyo o se escribio en cache, asi que cada token cae en una sola clave y
    el coste no se cuenta dos veces. Lo que no venga, no se inventa.

    Vive aqui y no en la capa de agentes porque tiene dos clientes: la llamada
    de §5 y el hook de §22, que recibe el mismo
    reparto del tool `Agent`.
    """
    if not bruto:
        return None
    if isinstance(bruto, dict):
        def leer(campo):
            return bruto.get(campo)
    else:
        def leer(campo):
            return getattr(bruto, campo, None)

    reparto = {}
    for clave in ('input_tokens', 'output_tokens',
                  'cache_read_input_tokens', 'cache_creation_input_tokens'):
        valor = leer(clave)
        if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0:
            # Langfuse llama input y output a lo que el SDK llama *_tokens.
            reparto[{'input_tokens': 'input',
                     'output_tokens': 'output'}.get(clave, clave)] = valor
    return reparto or None


def id_de_traza(semilla):
    """Id de traza deterministo a partir de una semilla (§21).

    La traza se abre y se cierra en el mismo proceso, asi que nunca
    necesito esto. El camino delegado no: cada llamada a un subagente la observa
    un proceso distinto -el hook- y la reconstruccion desde el canon llega mucho
    despues. Sembrando el id con "sesion|tramo", todos ellos escriben en la
    misma traza sin tener que pasarse nada.
    """
    if not semilla:
        return None
    try:
        from langfuse import Langfuse
        return Langfuse.create_trace_id(seed=semilla)
    except Exception:
        return None


def sesion_de(proyecto):
    """Id de sesion de una novela, derivado del brief.

    Los capitulos son trazas sueltas y la sesion es lo que las junta en un
    libro (§20). El canon no guarda ningun id de proyecto -es fila unica-, asi
    que se deriva del brief: misma novela, misma sesion, sin tocar el esquema.
    """
    if not proyecto:
        return None
    semilla = '|'.join(str(proyecto.get(c) or '') for c in (
        'epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo'))
    return 'novela-' + hashlib.sha256(semilla.encode('utf-8')).hexdigest()[:12]


# --------------------------------------------------------------- objeto mudo

class _Muda:
    """Lo que devuelve la capa cuando las trazas estan apagadas.

    Acepta todo y no hace nada, para que quien llama no tenga que preguntar si
    hay trazas antes de cada linea.
    """

    def actualizar(self, **_):
        pass

    def nota(self, *_, **__):
        pass


MUDA = _Muda()


class _Viva:
    """Envoltorio de una observacion de Langfuse.

    Existe para que el resto del paquete hable en los terminos de este repo y
    para que un fallo de la red no suba nunca al flujo.
    """

    def __init__(self, trazas, observacion):
        self._trazas = trazas
        self._obs = observacion

    def actualizar(self, **campos):
        try:
            self._obs.update(**campos)
        except Exception as e:
            self._trazas.averiado(e)

    def nota(self, nombre, valor, comentario=None, tipo=None):
        """Una puntuacion de Langfuse sobre esta observacion.

        Las notas del validador y el veredicto del gate (§8) entran por aqui:
        son las metricas de calidad del libro, y el sitio donde se miran es el
        mismo donde se mira la llamada que las produjo.
        """
        numerica = isinstance(valor, (int, float)) and not isinstance(valor, bool)
        try:
            self._obs.score(
                name=nombre,
                value=float(valor) if numerica else valor,
                comment=comentario,
                data_type=tipo or ('NUMERIC' if numerica else 'BOOLEAN'),
            )
        except Exception as e:
            self._trazas.averiado(e)


# ---------------------------------------------------------------------- capa

class Trazas:
    """La capa. Se construye siempre; estar activa es otra cosa (§20)."""

    def __init__(self, config, aviso=None):
        bloque = (config or {}).get('trazas') or {}
        self.entorno = bloque.get('entorno') or 'desarrollo'
        # La etiqueta que lleva toda traza de este repositorio. Hubo un tiempo
        # En Langfuse conviven proyectos: esta etiqueta es lo que separa las
        # trazas de este repositorio de las de cualquier otro.
        self.modo = 'delegado'
        self.aviso = aviso
        self._cliente = None
        self._roto = False
        self.motivo = None

        if not bloque.get('activas'):
            self.motivo = 'trazas.activas esta a false en el perfil'
            return
        self._cliente = self._arrancar()

    # ---- arranque

    def _arrancar(self):
        # El .env antes que el SDK: Langfuse lee el entorno al construirse, y un
        # cliente creado sin credencial se queda sin ella para siempre.
        cargar_entorno()
        faltan = [c for c in CLAVES if not os.environ.get(c)]
        if faltan:
            self.motivo = 'faltan en el entorno: {}'.format(', '.join(faltan))
            return None

        try:
            from langfuse import Langfuse
        except ImportError as e:
            self.motivo = 'falta el SDK: pip install "my-story-maker[trazas]" ({})'.format(e)
            return None

        try:
            return Langfuse(
                public_key=os.environ['LANGFUSE_PUBLIC_KEY'],
                secret_key=os.environ['LANGFUSE_SECRET_KEY'],
                base_url=os.environ.get('LANGFUSE_BASE_URL') or None,
                environment=self.entorno,
                release=__version__,
                mask=enmascarar,
            )
        except Exception as e:
            self.motivo = 'el cliente de Langfuse no arranco: {}'.format(e)
            return None

    @property
    def activa(self):
        return self._cliente is not None and not self._roto

    @property
    def api(self):
        """El cliente REST de Langfuse, para leer de vuelta lo que se mando.

        Sigue siendo esta la unica capa que sabe que Langfuse existe: quien
        quiere leer pide el cliente aqui en vez de construirse el suyo con la
        credencial por su cuenta.
        """
        return getattr(self._cliente, 'api', None) if self._cliente else None

    # ---- casos de afinado (AFINADO.md §5)
    #
    # Viven aqui, y no en `afinado.py`, por la regla de la cabecera: esta es la
    # unica pieza del repositorio que sabe que Langfuse existe. Y viven en
    # Langfuse, y no en el repositorio, porque el examinado tiene `Read` sobre
    # el proyecto y no puede tener delante el examen.

    def crear_conjunto(self, nombre, descripcion=None, metadata=None):
        if not self.activa:
            return False
        try:
            self._cliente.create_dataset(
                name=nombre, description=descripcion, metadata=metadata)
            return True
        except Exception as e:
            self.averiado(e)
            return False

    def subir_caso(self, conjunto, ident, entrada, clave, metadata=None):
        """Un caso: lo que ve el agente en `input` y la respuesta en
        `expected_output`. Reenviar el mismo id actualiza el caso."""
        if not self.activa:
            return False
        try:
            self._cliente.create_dataset_item(
                dataset_name=conjunto, id=ident, input=entrada,
                expected_output=clave, metadata=metadata)
            return True
        except Exception as e:
            self.averiado(e)
            return False

    def leer_casos(self, conjunto):
        if not self.activa:
            return []
        try:
            return [{'id': i.id, 'entrada': i.input, 'clave': i.expected_output,
                     'metadata': i.metadata}
                    for i in self._cliente.get_dataset(conjunto).items]
        except Exception as e:
            self.averiado(e)
            return []

    def averiado(self, error):
        """Un fallo de observabilidad no para la novela: se apaga y se cuenta.

        Es la idea de §13 llevada al otro extremo: alli un bloqueante que falla
        dos veces para el proceso porque afecta al libro; esto no afecta al
        libro, asi que se apaga y sigue.
        """
        if self._roto:
            return
        self._roto = True
        self.motivo = 'las trazas se apagaron tras un fallo: {}'.format(error)
        if self.aviso:
            self.aviso(self.motivo)

    # ---- observaciones

    @contextmanager
    def traza(self, nombre, entrada=None, sesion=None, etiquetas=None, metadata=None,
              tipo='span', trace_id=None, nombre_traza=None):
        """Una traza: una unidad de trabajo cerrada (§20).

        Son tres en este sistema -preparar, un capitulo y cerrar- y la sesion
        es lo que las junta en un libro.

        `trace_id` la fija desde fuera, para los escritores de §21 que no
        comparten proceso; `nombre_traza` mantiene el nombre estable aunque la
        raiz la abra uno u otro, y `tipo` permite que la observacion de mas
        arriba no sea un `span` cuando quien escribe es un solo agente.
        """
        if not self.activa:
            yield MUDA
            return

        # Solo se captura el fallo al ABRIR la observacion. Lo que lance el
        # cuerpo tiene que subir tal cual: un error del proveedor es del libro,
        # no de las trazas, y ademas asi lo registra el propio SDK al cerrar.
        pila = ExitStack()
        try:
            from langfuse import propagate_attributes
            pila.enter_context(propagate_attributes(
                session_id=sesion,
                tags=list(etiquetas or []) + [self.modo],
                version=__version__,
                metadata=metadata or None,
                trace_name=nombre_traza or nombre,
            ))
            campos = {'as_type': tipo, 'name': nombre, 'input': entrada}
            if trace_id:
                campos['trace_context'] = {'trace_id': trace_id}
            obs = pila.enter_context(
                self._cliente.start_as_current_observation(**campos))
        except Exception as e:
            pila.close()
            self.averiado(e)
            yield MUDA
            return

        with pila:
            yield _Viva(self, obs)

    @contextmanager
    def paso(self, nombre, tipo='span', entrada=None, metadata=None, modelo=None,
             parametros=None):
        """Un paso dentro de una traza. `tipo` es el de §20: agent, generation,
        retriever o evaluator.
        """
        if not self.activa:
            yield MUDA
            return

        campos = {'as_type': tipo, 'name': nombre, 'input': entrada,
                  'metadata': metadata or None}
        if modelo:
            campos['model'] = modelo
        if parametros:
            campos['model_parameters'] = parametros

        pila = ExitStack()
        try:
            obs = pila.enter_context(
                self._cliente.start_as_current_observation(**campos))
        except Exception as e:
            pila.close()
            self.averiado(e)
            yield MUDA
            return

        with pila:
            yield _Viva(self, obs)

    # ---- cierre

    def cerrar(self):
        """Vacia el buzon antes de que el proceso muera.

        El SDK manda en segundo plano; sin esto, la CLI -que es un proceso
        corto- termina y se lleva por delante las trazas del ultimo capitulo.
        """
        if self._cliente is None:
            return
        try:
            self._cliente.flush()
        except Exception as e:
            self.averiado(e)
