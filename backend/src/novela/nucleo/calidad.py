"""El bucle de control de calidad: enrutado, topes y evidencia.

Las unicas bifurcaciones del guion son el enrutado por severidad y el tope de
vueltas. Ningun agente enruta ni manda sobre otro: lo que decide la vuelta
siguiente es lo que hay escrito en las criticas, y lo decide esto.

Tres reglas sustituyen a lo que antes garantizaba el codigo: una dimension por
tarea, evidencia obligatoria, y doble pasada cuando dos agentes discrepan sobre
el mismo predicado.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from novela.ajustes import TOPE_DE_REGENERACIONES_POR_ESCENA, TOPE_DE_REVISIONES_POR_BORRADOR
from novela.almacen import Artefacto

# Enrutado por severidad. `bloqueante` regenera la escena, `mayor` entra en
# revision dirigida, `menor` y `sugerencia` esperan a la criba de pulido.
DESTINO_POR_SEVERIDAD: dict[str, str] = {
    "bloqueante": "regenerar_escena",
    "mayor": "revision_dirigida",
    "menor": "criba_de_pulido",
    "sugerencia": "criba_de_pulido",
}


@dataclass
class Enrutado:
    """Lo que sale de una criba, ya repartido por lo que puede parar."""

    regenerar_escena: list[Artefacto] = field(default_factory=list)
    revision_dirigida: list[Artefacto] = field(default_factory=list)
    criba_de_pulido: list[Artefacto] = field(default_factory=list)
    descartadas_sin_evidencia: list[Artefacto] = field(default_factory=list)

    @property
    def hay_bloqueantes(self) -> bool:
        return bool(self.regenerar_escena)

    @property
    def hay_mayores(self) -> bool:
        return bool(self.revision_dirigida)


def tiene_evidencia(critica: Artefacto) -> bool:
    """Una `Critica` sin evidencia citable se descarta antes de llegar al Revisor.

    Es lo que impide que el bucle se llene de impresiones, y el descarte se
    cuenta porque es lo que mide OBJ-04.
    """
    evidencia = critica.cuerpo.get("evidencia")
    return isinstance(evidencia, str) and bool(evidencia.strip())


def enrutar(criticas: Sequence[Artefacto]) -> Enrutado:
    """Reparte las criticas de una criba segun su severidad."""
    enrutado = Enrutado()
    for critica in criticas:
        if not tiene_evidencia(critica):
            enrutado.descartadas_sin_evidencia.append(critica)
            continue
        destino = DESTINO_POR_SEVERIDAD.get(critica.severidad or "")
        if destino is None:
            enrutado.descartadas_sin_evidencia.append(critica)
            continue
        getattr(enrutado, destino).append(critica)
    return enrutado


def queda_revision(revisiones_hechas: int) -> bool:
    """Dos revisiones dirigidas por borrador, y ni una mas."""
    return revisiones_hechas < TOPE_DE_REVISIONES_POR_BORRADOR


def queda_regeneracion(regeneraciones_hechas: int) -> bool:
    """Dos regeneraciones por escena, y ni una mas."""
    return regeneraciones_hechas < TOPE_DE_REGENERACIONES_POR_ESCENA


def se_acepta_con_criticas_abiertas(regeneraciones_hechas: int, revisiones_hechas: int) -> bool:
    """Agotado el tope, la escena se acepta con sus criticas abiertas anotadas
    y el capitulo se cierra marcado. Un bucle sin tope no es un bucle de
    calidad: es una forma de no terminar."""
    return not queda_regeneracion(regeneraciones_hechas) and not queda_revision(
        revisiones_hechas
    )


def hay_desacuerdo(constancias: Sequence[dict[str, Any]]) -> bool:
    """Dos agentes discrepan sobre el mismo predicado.

    Una constancia es lo que deja toda comprobacion: si el predicado se cumple
    o no. Que dos digan cosas distintas del mismo objeto y la misma dimension
    obliga a repetir con la proyeccion reducida al minimo.
    """
    por_predicado: dict[tuple[str, str], set[bool]] = {}
    for constancia in constancias:
        clave = (str(constancia.get("objeto")), str(constancia.get("dimension")))
        por_predicado.setdefault(clave, set()).add(bool(constancia.get("cumple")))
    return any(len(respuestas) > 1 for respuestas in por_predicado.values())


def rebajar_a_sugerencia(critica: Artefacto) -> Artefacto:
    """Si el desacuerdo persiste, la critica baja a `sugerencia` y se registra
    como caso ambiguo."""
    critica.severidad = "sugerencia"
    critica.cuerpo = {**critica.cuerpo, "caso_ambiguo": True}
    return critica
