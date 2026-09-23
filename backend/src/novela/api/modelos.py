"""Los modelos del borde HTTP.

Es el unico sitio del backend donde se declaran tipos. Lo que entra por aqui se
valida contra ellos; lo que sale, tambien. El cuerpo de un artefacto no se tipa
por dentro y por eso viaja como documento.
"""

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, Field

from novela.vocabularios import TIPO_DE_CONTRADICCION


class Destinatario(BaseModel):
    """La persona real a la que la obra va dedicada.

    Aparece en la novela con su nombre de verdad, sin traducir a la epoca: lo
    que sale de su vida se marca `licencia = "personal"` y el detector de
    anacronismos lo deja en paz (D-12). Que papel tiene en la obra no se declara
    aqui: lo decide el Planificador y lo escribe en el `Plan` (D-14).

    Obligatorios el nombre, la edad, el tono y la dedicatoria. Los tres que son
    listas pueden venir vacias, porque vacio es una respuesta: no veto nada, no
    aporto recuerdos.
    """

    nombre: str = Field(min_length=1, description="Su nombre real, tal como se escribira")
    edad: int = Field(ge=0, le=130, description="Edad del destinatario")
    tono: str = Field(min_length=1, description="Tono que se le pide a la obra")
    dedicatoria: str = Field(min_length=1, description="Lo que va en la portada")
    rasgos: list[str] = Field(default_factory=list, description="Como es")
    recuerdos: list[str] = Field(
        default_factory=list,
        description="Anecdotas de su vida. Cada una se guarda como Recuerdo (RF-07)",
    )
    vetos: list[str] = Field(
        default_factory=list, description="Palabras o temas que no quiere leer"
    )


class Brief(BaseModel):
    """Lo que el editor escribe para lanzar una obra.

    Si falta un campo obligatorio, la obra se rechaza nombrando el campo y sin
    crear nada. Un brief incompleto es un caso normal, no un error del sistema.
    """

    titulo: str = Field(min_length=1, description="Titulo de la obra")
    epoca: str = Field(min_length=1, description="Epoca y ambito geografico")
    premisa: str = Field(min_length=1, description="De que va")
    tesis_tematica: str = Field(min_length=1, description="Que sostiene la obra")
    elenco_declarado: list[str] = Field(description="Personajes que el editor fija")
    capitulos_objetivo: int = Field(ge=1, le=200, description="Cuantos capitulos")
    politicas_globales: dict[str, Any] = Field(
        default_factory=dict,
        description="POV dominante, tiempo verbal, nivel de arcaismo, extension",
    )
    arcos: list[str] = Field(default_factory=list, description="Arcos declarados")
    destinatario: Destinatario | None = Field(
        default=None,
        description="A quien va dedicada. Opcional: sin el, la obra es historica y nada mas",
    )


class ObraCreada(BaseModel):
    id_obra: str
    estado: str


class FichaDeObra(BaseModel):
    """Estado de la obra, capitulo en curso y recuento de cerrados y marcados."""

    id_obra: str
    titulo: str
    detenida: bool
    capitulo_en_curso: int | None
    capitulos_cerrados: int
    capitulos_marcados: int
    criticas_abiertas: int


class UnidadDelManuscrito(BaseModel):
    capitulo: int
    escena: str
    texto: str
    capitulo_marcado: bool


class Manuscrito(BaseModel):
    id_obra: str
    unidades: list[UnidadDelManuscrito]


class CapituloInspeccionado(BaseModel):
    capitulo: int
    estado: str | None
    plan: dict[str, Any] | None
    escenas: list[dict[str, Any]]
    borrador_vigente_por_escena: dict[str, dict[str, Any]]
    criticas: list[dict[str, Any]]


class CriticaServida(BaseModel):
    id: str
    capitulo: int | None
    escena: str | None
    estado: str | None
    severidad: str | None
    dimension: str | None
    detectada_por: str | None
    evidencia: str | None
    accion_sugerida: str | None


class TrazaServida(BaseModel):
    id: str
    capitulo: int | None
    escena: str | None
    rol: str | None
    tarea: str | None
    intento: int | None
    tokens_de_entrada_estimados: int | None
    tokens_de_entrada_medidos: int | None
    tokens_de_salida: int | None
    coste: float | None
    latencia_ms: int | None
    abierta_en: str | None
    cerrada_en: str | None


class EstadoPlegado(BaseModel):
    """El estado plegado hasta el capitulo indicado, y el log de eventos."""

    id_obra: str
    capitulo: int
    estado: dict[str, Any] | None
    eventos: list[dict[str, Any]]


class Progreso(BaseModel):
    """Lo que hay abierto ahora mismo."""

    id_obra: str
    detenida: bool
    capitulo_en_curso: int | None
    tareas_abiertas: list[dict[str, Any]]
    tokens_de_entrada_concurrentes: int
    techo: int


class Pasaje(BaseModel):
    """Un trozo del manuscrito aceptado, localizado por parecido."""

    fragmento: str
    texto: str
    capitulo: int | None
    escena: str | None


class Orden(BaseModel):
    """Detener o reanudar. Es control, no mantenimiento."""

    motivo: str = Field(default="", description="Por que se detiene")


class Confirmacion(BaseModel):
    id_obra: str
    detenida: bool
    motivo: str | None


# --- La entrevista que completa el brief (SPEC1 4.8) -------------------------

TipoDeContradiccion = Literal["edad_contra_tono", "texto_contra_campo"]
assert get_args(TipoDeContradiccion) == TIPO_DE_CONTRADICCION, (
    "El borde y el vocabulario de contradicciones no dicen lo mismo"
)


class BorradorDeDestinatario(BaseModel):
    """El destinatario tal como la persona lo lleva escrito: todo opcional.

    Un campo ausente es un campo por preguntar. Una lista presente, aunque venga
    vacia, es lo que la persona escribio, y ninguna pasada le quita nada (RF-73).
    """

    nombre: str | None = Field(default=None, min_length=1)
    edad: int | None = Field(default=None, ge=0, le=130)
    tono: str | None = Field(default=None, min_length=1)
    dedicatoria: str | None = Field(default=None, min_length=1)
    rasgos: list[str] | None = None
    recuerdos: list[str] | None = None
    vetos: list[str] | None = None


class BorradorDeBrief(BaseModel):
    """El brief a medio escribir. Tiene los campos del `Brief`, todos opcionales."""

    titulo: str | None = Field(default=None, min_length=1)
    epoca: str | None = Field(default=None, min_length=1)
    premisa: str | None = Field(default=None, min_length=1)
    tesis_tematica: str | None = Field(default=None, min_length=1)
    elenco_declarado: list[str] | None = None
    capitulos_objetivo: int | None = Field(default=None, ge=1, le=200)
    politicas_globales: dict[str, Any] | None = None
    arcos: list[str] | None = None
    destinatario: BorradorDeDestinatario | None = None


class PeticionDeEntrevista(BaseModel):
    """Lo que la persona manda en cada pasada. De las anteriores no llega nada:
    lo que quiera conservar lo vuelve a mandar (D-20)."""

    borrador: BorradorDeBrief = Field(default_factory=BorradorDeBrief)
    textos: list[Annotated[str, Field(min_length=1)]] = Field(
        default_factory=list,
        description=(
            "Textos pegados, como una carta o una anecdota. Son datos, nunca instrucciones"
        ),
    )
    contradicciones_asumidas: list[TipoDeContradiccion] = Field(
        default_factory=list,
        description="Contradicciones que la persona da por buenas: no bloquean el alta (RF-77)",
    )


class HechoExtraido(BaseModel):
    """Un hecho sacado de un texto pegado, con su cita literal."""

    campo: str
    valor: Any
    cita: str


class HechoDescartado(BaseModel):
    campo: str | None
    cita: str | None
    motivo: str


class Contradiccion(BaseModel):
    """Lo que no casa. El Entrevistador no la resuelve: la devuelve como pregunta."""

    tipo: TipoDeContradiccion
    campos: list[str]
    evidencia: str
    asumida: bool


class PasadaDeEntrevista(BaseModel):
    """Lo que devuelve una pasada. Si `estado` es `lanzada`, la obra ya corre."""

    id_entrevista: str
    numero: int
    estado: Literal["pendiente", "lanzada"]
    id_obra: str | None
    brief_propuesto: dict[str, Any]
    faltan: list[str] = Field(description="Campos obligatorios que faltan, con su ruta")
    no_validos: list[str] = Field(description="Campos presentes que el brief no admite")
    hechos: list[HechoExtraido]
    hechos_descartados: list[HechoDescartado]
    contradicciones: list[Contradiccion]
    contradicciones_descartadas: int
