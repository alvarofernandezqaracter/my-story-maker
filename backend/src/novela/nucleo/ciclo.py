"""El ciclo de vida de un capitulo, que es lo que el caminante recorre.

`Planificado` a `Redactado` a `Validado`, con vuelta a `Redactado` por critica
bloqueante y a `EnRevision` por criticas mayores, y de `Validado` a `Aceptado`
cuando no quedan bloqueantes. De `Aceptado` a `Cerrado` es el paso que publica
los hechos y olvida el andamio: hasta que un capitulo no cierra, sus eventos no
existen para el resto del sistema. Un plan rechazado va a `Descartado`.

El paso de `Redactado` a `Validado` lo dan las cribas de agentes. No hay
validadores deterministas en el sistema.
"""

TRANSICIONES: dict[str, frozenset[str]] = {
    "planificado": frozenset({"redactado", "descartado"}),
    "redactado": frozenset({"validado"}),
    "validado": frozenset({"redactado", "en_revision", "aceptado"}),
    "en_revision": frozenset({"validado"}),
    "aceptado": frozenset({"cerrado"}),
    "cerrado": frozenset(),
    "descartado": frozenset(),
}

ESTADOS_FINALES: frozenset[str] = frozenset({"cerrado", "descartado"})


class TransicionImposible(Exception):
    """Se ha pedido un salto que el ciclo de vida no contempla."""


def transitar(desde: str, hasta: str) -> str:
    if desde not in TRANSICIONES:
        raise TransicionImposible(f"{desde!r} no es un estado del capitulo")
    if hasta not in TRANSICIONES[desde]:
        raise TransicionImposible(f"de {desde!r} no se pasa a {hasta!r}")
    return hasta


def siguiente_tras_criba(hay_bloqueantes: bool, hay_mayores: bool) -> str:
    """A donde va un capitulo `validado` segun lo que dejo la criba."""
    if hay_bloqueantes:
        return "redactado"
    if hay_mayores:
        return "en_revision"
    return "aceptado"
