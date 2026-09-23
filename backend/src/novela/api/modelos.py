"""Los modelos del borde HTTP.

Es el unico sitio del backend donde se declaran tipos. Lo que entra por aqui se
valida contra ellos; lo que sale, tambien. El cuerpo de un artefacto no se tipa
por dentro y por eso viaja como documento.
"""

from typing import Any

from pydantic import BaseModel, Field


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
