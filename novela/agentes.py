# §5 Agentes y §12 modo de ejecucion. Toda llamada a un agente pasa por aqui,
# asi que el resto del harness no sabe si esta corriendo contra la API o contra
# la capa simulada. Ningun agente escribe en el canon: devuelven una propuesta
# que el harness valida (§9) y persiste.
from .claude_code import llamar_a_claude_code
from .proveedor import llamar_al_proveedor
from .simulado import AGENTES_SIMULADOS
from .skills import instrucciones_de
from .validadores import comprobar_salida_de_agente


class ParadaDelProceso(Exception):
    """El proceso para y deja el estado escrito, en vez de insistir (§9, §13)."""

    def __init__(self, mensaje, detalles=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = list(detalles) if detalles else []


class Agentes:
    def __init__(self, config, raices=None):
        self.config = config
        self.raices = dict(raices) if raices else {}
        self.registro = []
        # Gancho opcional: se llama justo antes de cada llamada a un agente.
        # Lo usa la interfaz de §19 para contar en vivo quien esta trabajando;
        # sin nadie escuchando no cambia nada de lo que hace esta clase.
        self.observador = None

    @property
    def modo(self):
        return self.config['ejecucion']['modo']

    def modelo_de(self, rol):
        return self.config['modelo_por_rol'][rol]

    def _llamar(self, rol, entrada):
        """Una llamada cruda, sin validar. Reintenta una vez ante error de proveedor."""
        if self.modo == 'simulado':
            fn = AGENTES_SIMULADOS.get(rol)
            if not fn:
                raise ValueError('rol sin agente simulado: {}'.format(rol))
            return fn(entrada)

        instrucciones = instrucciones_de(rol, **self.raices)['texto']
        modelo = self.modelo_de(rol)
        # El unico sitio donde se elige transporte: API oficial o CLI de Claude
        # Code. De aqui hacia arriba nadie sabe cual esta activo (§12).
        llamar = llamar_a_claude_code if self.modo == 'claude_code' else llamar_al_proveedor
        try:
            return llamar(rol, modelo, instrucciones, entrada)['salida']
        except Exception as primera:
            try:
                return llamar(rol, modelo, instrucciones, entrada)['salida']
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
        """
        ultimo = None
        for vuelta in (1, 2):
            if self.observador:
                self.observador(rol, vuelta)
            salida = self._llamar(rol, entrada)
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
                return {'salida': salida, 'comprobaciones': forma.comprobaciones + extra}
            ultimo = bloqueantes

        raise ParadaDelProceso(
            'el rol {} no supera las comprobaciones deterministas dos veces seguidas'.format(rol),
            ['{}: {}'.format(c['id'], d) for c in ultimo for d in c['detalles']],
        )
