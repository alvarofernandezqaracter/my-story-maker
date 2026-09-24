"""Los modelos del borde HTTP.

Es el unico sitio del backend donde se declaran tipos. Lo que entra por aqui se
valida contra ellos; lo que sale, tambien. El cuerpo de un artefacto no se tipa
por dentro y por eso viaja como documento.
"""

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, Field

from novela.vocabularios import TIPO_DE_CONTRADICCION, VALIDADOR_DE_LA_PUERTA


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
    tesis_tematica: str | None = Field(
        default=None,
        min_length=1,
        description="Que sostiene la obra. Opcional: sin ella no hay tesis declarada (D-50)",
    )
    elenco_declarado: list[str] = Field(
        default_factory=list,
        description=(
            "Personajes que el editor fija. Vacio: los decide el Constructor de mundo (D-50)"
        ),
    )
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
    version_en_curso: int = Field(description="La ultima version, la unica que se produce")
    version_publicada: int | None = Field(description="La de la ultima publicacion, si la hay")
    motivo_de_la_detencion: str | None = Field(
        default=None,
        description=(
            "Por que esta detenida: la tarea, lo que fallo y su traza. Vacio si no (RI-17)"
        ),
    )


class UnidadDelManuscrito(BaseModel):
    capitulo: int
    escena: str
    texto: str
    capitulo_marcado: bool


class Manuscrito(BaseModel):
    id_obra: str
    version: int = Field(description="La version que se sirve")
    publicada: bool = Field(description="Si esa version es la publicada")
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


class DecisionDePolicy(BaseModel):
    """Una coincidencia de lo vetado y lo que `policy` hizo con ella (RI-16)."""

    id: int
    id_traza: str
    capitulo: int | None
    escena: str | None
    tarea: str | None
    intento: int | None
    decision: Literal["devuelto_al_agente", "intento_fallido"]
    nivel: Literal["global", "palabra_del_comprador", "tema_del_comprador"]
    termino: str = Field(description="El veto tal como esta en su lista")
    encontrado: str = Field(description="Lo que casó, tal como esta escrito en la prosa")
    registrada_en: str


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
    ganchos: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Lo que dijeron los hooks del paso durante la sesion y su veredicto final. "
            "Vacio si el paso no lleva hooks (RI-15)"
        ),
    )


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


class HechoDeLaBiblia(BaseModel):
    """Una ficha del mundo que el texto nombra, con los capitulos en que se usa.

    Los capitulos se derivan de las `Mencion` que el Archivero anota al cerrar
    cada capitulo; la ficha no los guarda (RF-84).
    """

    id: str
    tipo: str
    nombre: str | None
    licencia: str | None
    capitulos: list[int]


class Presente(BaseModel):
    """Un personaje presente en un suceso, con su fecha de nacimiento."""

    id: str
    nombre: str | None
    nacimiento: str | None = Field(description="Fecha ISO parcial: AAAA, AAAA-MM o AAAA-MM-DD")


class Suceso(BaseModel):
    """Una fila de la cronologia: un `EventoEstado` o un `Evento` del mundo."""

    origen: str = Field(description="evento_de_estado o evento_del_mundo")
    id: str
    capitulo: int | None
    suceso: str | None
    momento: str | None = Field(description="Fecha ISO parcial: AAAA, AAAA-MM o AAAA-MM-DD")
    lugar: str | None
    presentes: list[Presente]


class Cronologia(BaseModel):
    """Los sucesos de la obra en orden. Es una vista: se deriva al pedirla."""

    id_obra: str
    sucesos: list[Suceso]


class Orden(BaseModel):
    """Detener o reanudar. Es control, no mantenimiento."""

    motivo: str = Field(default="", description="Por que se detiene")


class Confirmacion(BaseModel):
    id_obra: str
    detenida: bool
    motivo: str | None


# --- Las versiones de la obra (SPEC1 4.12) ---------------------------------


class PeticionDeRehacer(BaseModel):
    """Rehacer desde un capitulo: de el al final se reescribe (D-42)."""

    desde_capitulo: int = Field(ge=1, description="Primer capitulo que se reescribe")


class VersionDeLaObra(BaseModel):
    """Una version con su base y lo que cambio respecto de ella."""

    numero: int
    base: int | None = Field(description="La version de la que sale; la 1 no sale de ninguna")
    capitulos_cambiados: list[int] = Field(description="Los que reescribe respecto de su base")
    creada_en: str
    terminada_en: str | None
    terminada: bool
    publicada: bool = Field(description="Si es la de la ultima publicacion")


class VersionAbierta(BaseModel):
    id_obra: str
    version: int
    capitulos_cambiados: list[int]
    estado: str


class Publicacion(BaseModel):
    id_obra: str
    version: int
    publicada_en: str


# --- La puerta de publicacion (SPEC1 4.15) -----------------------------------

ValidadorDeLaPuerta = Literal["esquema", "nombres", "longitud", "elementos_personalizados"]
assert get_args(ValidadorDeLaPuerta) == VALIDADOR_DE_LA_PUERTA, (
    "El borde y el vocabulario de validadores de la puerta no dicen lo mismo"
)


class FalloDeLaPuerta(BaseModel):
    """Lo que no pasa, de que validador y en que capitulo."""

    validador: ValidadorDeLaPuerta
    capitulo: int | None = Field(description="Vacio si el fallo no es de ningun capitulo")
    detalle: str


class PuertaDePublicacion(BaseModel):
    """El resultado de pasar la puerta sobre una version. Se deriva al pedirlo."""

    id_obra: str
    version: int
    terminada: bool = Field(description="Sin terminar no se publica aunque pase")
    pasa: bool
    fallos: list[FalloDeLaPuerta]


class RechazoDePublicacion(BaseModel):
    """Por que no se publico. `puerta` viene si lo que fallo fue la puerta."""

    detail: str
    puerta: PuertaDePublicacion | None = None


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
