# §5 Agentes y §12 modo de ejecucion. Toda llamada a un agente pasa por aqui,
# asi que el resto del harness no sabe si esta corriendo contra la API o contra
# la capa simulada. Ningun agente escribe en el canon: devuelven una propuesta
# que el harness valida (§9) y persiste.
#
# Por el mismo sitio pasa la observabilidad de §20: aqui nace la observacion
# `agent` de cada rol y la `generation` de cada invocacion del modelo. Es el
# unico sitio donde puede nacer, porque es el unico por el que pasan todas.
from .claude_code import PARAMETROS as PARAMETROS_CLI, llamar_a_claude_code
from .proveedor import (
    PARAMETROS as PARAMETROS_API, instruccion_de_formato, llamar_al_proveedor)
from .simulado import AGENTES_SIMULADOS
from .skills import instrucciones_de
from .trazas import Trazas
from .validadores import comprobar_salida_de_agente

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


class ParadaDelProceso(Exception):
    """El proceso para y deja el estado escrito, en vez de insistir (§9, §13)."""

    def __init__(self, mensaje, detalles=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = list(detalles) if detalles else []


def reparto_de_tokens(bruto):
    """Traduce el gasto de una llamada al reparto que espera Langfuse (§20).

    Las cubetas no se solapan: `input_tokens` de Anthropic ya viene sin lo que
    se leyo o se escribio en cache, asi que cada token cae en una sola clave y
    el coste no se cuenta dos veces. Lo que no venga, no se inventa.
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


class Agentes:
    def __init__(self, config, raices=None, aviso=None):
        self.config = config
        self.raices = dict(raices) if raices else {}
        self.registro = []
        # Gancho opcional: se llama justo antes de cada llamada a un agente.
        # Lo usa la interfaz de §19 para contar en vivo quien esta trabajando;
        # sin nadie escuchando no cambia nada de lo que hace esta clase.
        self.observador = None
        self.trazas = Trazas(config, aviso=aviso)

    @property
    def modo(self):
        return self.config['ejecucion']['modo']

    def modelo_de(self, rol):
        return self.config['modelo_por_rol'][rol]

    def _generar(self, rol, entrada, vuelta, envio):
        """Una invocacion del modelo, observada como `generation` de §20.

        Una por invocacion y nunca una que englobe el bucle: lo que interesa ver
        despues es que contesto el modelo en cada vuelta, no solo en la ultima.
        `vuelta` es la de las comprobaciones de §9 y `envio` la del reintento de
        transporte de §13; son dos bucles distintos y conviene distinguirlos.
        """
        nombre = GENERACIONES.get(rol, 'llamar-agente')
        marcas = {'vuelta': vuelta, 'envio': envio, 'transporte': self.modo}

        if self.modo == 'simulado':
            fn = AGENTES_SIMULADOS.get(rol)
            if not fn:
                raise ValueError('rol sin agente simulado: {}'.format(rol))
            with self.trazas.paso(nombre, 'generation', entrada=entrada,
                                  modelo='simulado', metadata=marcas) as gen:
                salida = fn(entrada)
                gen.actualizar(output=salida)
            return salida

        instrucciones = instrucciones_de(rol, **self.raices)['texto']
        modelo = self.modelo_de(rol)
        # El unico sitio donde se elige transporte: API oficial o CLI de Claude
        # Code. De aqui hacia arriba nadie sabe cual esta activo (§12).
        llamar = llamar_a_claude_code if self.modo == 'claude_code' else llamar_al_proveedor
        parametros = PARAMETROS_CLI if self.modo == 'claude_code' else PARAMETROS_API

        # Lo que el modelo ve, entero y en el orden en que lo ve. Es lo unico
        # que explica despues por que contesto lo que contesto.
        conversacion = [
            {'role': 'system', 'content': instrucciones + instruccion_de_formato(rol)},
            {'role': 'user', 'content': entrada},
        ]
        with self.trazas.paso(nombre, 'generation', entrada=conversacion, modelo=modelo,
                              metadata=marcas, parametros=parametros) as gen:
            respuesta = llamar(rol, modelo, instrucciones, entrada)
            gen.actualizar(output=respuesta['salida'],
                           usage_details=reparto_de_tokens(respuesta.get('uso')))
        return respuesta['salida']

    def _llamar(self, rol, entrada, vuelta):
        """Una llamada cruda, sin validar. Reintenta una vez ante error de proveedor."""
        if self.modo == 'simulado':
            return self._generar(rol, entrada, vuelta, 1)
        try:
            return self._generar(rol, entrada, vuelta, 1)
        except Exception as primera:
            try:
                return self._generar(rol, entrada, vuelta, 2)
            except Exception as segunda:
                raise ParadaDelProceso(
                    'el proveedor fallo dos veces en el rol {}'.format(rol),
                    [str(primera), str(segunda)],
                ) from segunda

    def pedir(self, rol, entrada, comprobaciones_extra=None):
        """Llamada con las comprobaciones de forma de §9 (VD-01 y VD-02) y las extra
        que pase quien llama.

        Un bloqueante que falla dos veces seguidas sobre el mismo artefacto para
        el proceso: no hay reintento infinito.

        En la traza es una observacion `agent` (§20) con dentro una `generation`
        por vuelta: asi se ve si un rol acerto a la primera o si lo salvo el
        reintento.
        """
        with self.trazas.paso(rol, 'agent', entrada=entrada,
                              metadata={'modelo': self.config['modelo_por_rol'].get(rol),
                                        'modo': self.modo}) as agente:
            ultimo = None
            for vuelta in (1, 2):
                if self.observador:
                    self.observador(rol, vuelta)
                salida = self._llamar(rol, entrada, vuelta)
                forma = comprobar_salida_de_agente(rol, salida)

                extra = []
                if forma.ok and comprobaciones_extra:
                    propuestas = comprobaciones_extra(salida)
                    extra = [propuestas] if isinstance(propuestas, dict) else list(propuestas)

                bloqueantes = forma.bloqueantes + [
                    c for c in extra if not c['ok'] and c['severidad'] == 'bloqueante'
                ]

                self.registro.append({'rol': rol, 'vuelta': vuelta, 'ok': not bloqueantes})

                if not bloqueantes:
                    agente.actualizar(output=salida, metadata={'vueltas': vuelta})
                    return {'salida': salida, 'comprobaciones': forma.comprobaciones + extra}
                ultimo = bloqueantes
                # La vuelta suspendida se marca en la observacion: sin esto, un
                # rol que acierta a la segunda parece que acerto a la primera.
                agente.actualizar(
                    level='WARNING',
                    status_message='vuelta {}: {}'.format(
                        vuelta, ', '.join(c['id'] for c in bloqueantes)))

            detalles = ['{}: {}'.format(c['id'], d) for c in ultimo for d in c['detalles']]
            agente.actualizar(level='ERROR', status_message='; '.join(detalles)[:900])
            raise ParadaDelProceso(
                'el rol {} no supera las comprobaciones deterministas dos veces'
                ' seguidas'.format(rol),
                detalles,
            )
