"""El ejecutor fingido y el catalogo de contratos de mentira.

Devuelven artefactos preparados en vez de llamar a un agente. Es lo que permite
recorrer el guion entero sin gastar ni producir novela, y es lo primero que
debe existir: mientras no exista, cualquier fallo del guion se descubre
gastando.

Vive en `tests/` a proposito. El material con el que se juzga a un agente no
puede estar donde el agente puede leerlo: si esto viviera en `tareas/`, una
proyeccion podria arrastrarlo.
"""

from dataclasses import dataclass, field
from typing import Any

from novela.almacen import Artefacto
from novela.nucleo.caminante import Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana

ESCENAS_POR_CAPITULO = 3


@dataclass
class CasoSembrado:
    """Un defecto puesto a proposito, para ver si el guion reacciona."""

    paso: int
    indice_de_escena: int
    dimension: str
    severidad: str
    veces: int = 1


@dataclass
class EjecutorFingido:
    """Contesta lo que contestaria un agente, sin agente."""

    sembrados: list[CasoSembrado] = field(default_factory=list)
    sin_evidencia: bool = False
    # Lo que contesta el Entrevistador fingido: sus hechos y contradicciones, y
    # los artefactos que no deberia devolver y el backend no debe guardar.
    entrevista: dict[str, Any] = field(default_factory=dict)
    artefactos_de_entrevista: list[Artefacto] = field(default_factory=list)
    llamadas: list[Encargo] = field(default_factory=list)
    ventanas: list[Ventana] = field(default_factory=list)
    _orden_de_escenas: list[str] = field(default_factory=list)
    _vistas: dict[tuple[Any, ...], int] = field(default_factory=dict)
    _ventana: Ventana | None = None

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        self.llamadas.append(encargo)
        self.ventanas.append(ventana)
        self._ventana = ventana
        if encargo.escena:
            self._ver_escena(encargo.escena)
        metodo = getattr(self, f"_{encargo.tarea}", None)
        if metodo is None:
            return Resultado(salida=f"{encargo.tarea} sin nada que escribir")
        return metodo(encargo)

    # --- Una respuesta por tipo de tarea ----------------------------------

    def _poblar_mundo(self, encargo: Encargo) -> Resultado:
        fichas = [
            Artefacto("Personaje", {"nombre": "Ines de Salcedo", "licencia": "plausible"}),
            Artefacto("Lugar", {"nombre": "Sevilla", "licencia": "canon"}),
        ]
        return Resultado(artefactos=fichas, salida="mundo poblado")

    def _planificar(self, encargo: Encargo) -> Resultado:
        capitulo = Artefacto(
            "Capitulo",
            {"numero": encargo.capitulo, "titulo": f"Capitulo {encargo.capitulo}"},
            capitulo=encargo.capitulo,
            estado="planificado",
        )
        artefactos: list[Artefacto] = [capitulo]
        for orden in range(1, ESCENAS_POR_CAPITULO + 1):
            artefactos.append(
                Artefacto(
                    "Escena",
                    {
                        "pov": "per_0001",
                        "elenco_presente": [],
                        "marco": {"lugar": "lug_0001", "instante": f"1587-04-0{orden}"},
                        "objetivo": "imprimir el pliego",
                        "obstaculo": "el alguacil ronda la calle",
                        "cambio_de_valor": {"entra": "confiada", "sale": "acorralada"},
                        "funcion_estructural": "escalada",
                    },
                    capitulo=encargo.capitulo,
                    orden=orden,
                    estado="planificado",
                )
            )
        artefactos.append(
            Artefacto("Plan", {"escenas": ESCENAS_POR_CAPITULO}, capitulo=encargo.capitulo,
                      estado="planificado")
        )
        return Resultado(artefactos=artefactos, salida="plan escrito")

    def _documentar(self, encargo: Encargo) -> Resultado:
        return Resultado(
            artefactos=[
                Artefacto(
                    "Fuente",
                    {"cita": "Ordenanzas de la imprenta, 1558", "tipo": "primaria"},
                    capitulo=encargo.capitulo,
                )
            ],
            salida="una fuente recogida",
        )

    def _redactar(self, encargo: Encargo) -> Resultado:
        vez = self._contar(("redactar", encargo.escena))
        return Resultado(
            artefactos=[
                Artefacto(
                    "Borrador",
                    {"texto": f"Version {vez} de la escena."},
                    capitulo=encargo.capitulo,
                    escena=encargo.escena,
                    estado="redactado",
                )
            ],
            salida="escena redactada",
        )

    def _verificar(self, encargo: Encargo) -> Resultado:
        return self._comprobar(encargo)

    def _juzgar(self, encargo: Encargo) -> Resultado:
        return self._comprobar(encargo)

    def _editar_estilo(self, encargo: Encargo) -> Resultado:
        if encargo.dimension is not None:
            return self._comprobar(encargo)
        # La costura del capitulo: un borrador de superficie por escena. Las
        # escenas salen de la ventana, que es lo unico que un agente ve.
        escenas = self._escenas_de_la_ventana()
        return Resultado(
            artefactos=[
                Artefacto(
                    "Borrador",
                    {"texto": "Version cosida de la escena."},
                    capitulo=encargo.capitulo,
                    escena=escena,
                    estado="redactado",
                )
                for escena in escenas
            ],
            salida="capitulo cosido",
        )

    def _revisar(self, encargo: Encargo) -> Resultado:
        return Resultado(
            artefactos=[
                Artefacto(
                    "Revision",
                    {"atendidas": 1, "rechazadas": 0},
                    capitulo=encargo.capitulo,
                    escena=encargo.escena,
                ),
                Artefacto(
                    "Borrador",
                    {"texto": "Version revisada de la escena."},
                    capitulo=encargo.capitulo,
                    escena=encargo.escena,
                    estado="redactado",
                ),
            ],
            salida="escena revisada",
        )

    def _plegar(self, encargo: Encargo) -> Resultado:
        """Pliega de verdad, aunque de mentira: estado en N-1 mas los eventos de N.

        Que el pliegue sea incremental es lo que permite comprobar la propiedad
        —replegar desde N da lo mismo que plegar el log entero— sin depender de
        lo que conteste un modelo.
        """
        anterior = {}
        if self._ventana is not None:
            anterior = self._ventana.materiales.get("estado_en_n_menos_1") or {}
        plegados = list(anterior.get("capitulos_plegados") or [])
        plegados.append(encargo.capitulo)
        return Resultado(
            artefactos=[
                Artefacto(
                    "EventoEstado",
                    {
                        "tipo_de_evento": "viaja_a",
                        "sujeto": "per_0001",
                        "fecha_resultante": f"1587-04-0{encargo.capitulo}",
                        "lugar_resultante": f"lug_000{encargo.capitulo}",
                    },
                    capitulo=encargo.capitulo,
                )
            ],
            estado_en_n={
                "capitulos_plegados": plegados,
                "ubicacion": f"lug_000{encargo.capitulo}",
            },
            salida="capitulo plegado",
        )

    def _entrevistar(self, encargo: Encargo) -> Resultado:
        return Resultado(
            artefactos=list(self.artefactos_de_entrevista),
            constancia=dict(self.entrevista),
            salida="pasada de entrevista",
            tokens_de_entrada_medidos=(self._ventana.tokens if self._ventana else 0) + 10_000,
            tokens_de_salida=120,
            coste=0.001,
            latencia_ms=5,
        )

    def _destilar(self, encargo: Encargo) -> Resultado:
        return Resultado(
            artefactos=[
                Artefacto(
                    "ResumenCapitulo",
                    {"que_paso": "Imprimieron el pliego", "que_quedo": "el alguacil sospecha"},
                    capitulo=encargo.capitulo,
                )
            ],
            salida="capitulo destilado",
        )

    def _auditar(self, encargo: Encargo) -> Resultado:
        return self._comprobar(encargo)

    # --- Apoyos -------------------------------------------------------------

    def _comprobar(self, encargo: Encargo) -> Resultado:
        """Deja constancia de que el predicado se cumple, o siembra el defecto."""
        indice = self._indice_de_escena(encargo)
        for caso in self.sembrados:
            if (
                caso.paso == encargo.paso
                and caso.dimension == encargo.dimension
                and caso.indice_de_escena == indice
            ):
                vez = self._contar(("sembrado", caso.paso, caso.dimension, indice))
                if vez <= caso.veces:
                    return Resultado(
                        artefactos=[
                            Artefacto(
                                "Critica",
                                {
                                    "objeto": encargo.escena,
                                    "evidencia": self._evidencia(),
                                    "accion_sugerida": "narrar solo lo accesible al foco",
                                },
                                capitulo=encargo.capitulo,
                                escena=encargo.escena,
                                severidad=caso.severidad,
                                dimension=caso.dimension,
                                rol=encargo.rol,
                                estado="abierta",
                            )
                        ],
                        salida="defecto encontrado",
                    )
        return Resultado(
            constancia={
                "objeto": encargo.escena,
                "dimension": encargo.dimension,
                "cumple": True,
            },
            salida="el predicado se cumple",
        )

    def _evidencia(self) -> str:
        return "" if self.sin_evidencia else "«supo que ya habia firmado»"

    def _ver_escena(self, escena: str) -> None:
        if escena not in self._orden_de_escenas:
            self._orden_de_escenas.append(escena)

    def _indice_de_escena(self, encargo: Encargo) -> int:
        if encargo.escena in self._orden_de_escenas:
            return self._orden_de_escenas.index(encargo.escena)
        return -1

    def _escenas_de_la_ventana(self) -> list[str]:
        if self._ventana is None:
            return []
        escenas: list[str] = []
        for fila in self._ventana.materiales.get("texto_producido") or []:
            escena = fila.get("escena")
            if escena and escena not in escenas:
                escenas.append(escena)
        return escenas

    def _contar(self, clave: tuple[Any, ...]) -> int:
        self._vistas[clave] = self._vistas.get(clave, 0) + 1
        return self._vistas[clave]



class CatalogoFingido:
    """Contratos de verificacion de mentira, con su proyeccion minima."""

    def contrato(self, tarea: str, dimension: str | None) -> dict[str, Any] | None:
        if dimension is None:
            return None
        return {
            "dimension": dimension,
            "predicado": f"se cumple {dimension}",
            "severidad_por_defecto": "bloqueante",
            "evidencia_aceptada": "fragmento citado del texto",
        }

    def proyeccion_minima(self, tarea: str, dimension: str | None) -> tuple[str, ...]:
        return ()
