# §20 Observabilidad. Capa unica de trazas contra Langfuse, con la misma regla
# que la capa de agentes de §5: de aqui hacia arriba nadie sabe si hay trazas.
# Cuando estan apagadas, o cuando falta el SDK o la credencial, todo lo de este
# fichero devuelve objetos mudos y el harness corre exactamente igual.
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

    Existe para que el resto del harness hable en los terminos de este repo y
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
        self.modo = ((config or {}).get('ejecucion') or {}).get('modo') or 'simulado'
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
    def traza(self, nombre, entrada=None, sesion=None, etiquetas=None, metadata=None):
        """Una traza: una unidad de trabajo cerrada (§20).

        Son tres en este sistema -preparar, un capitulo y cerrar- y la sesion
        es lo que las junta en un libro.
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
            ))
            obs = pila.enter_context(self._cliente.start_as_current_observation(
                as_type='span', name=nombre, input=entrada))
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
