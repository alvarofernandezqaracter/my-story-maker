"""Las versiones de la obra: rehacer desde un capitulo y publicar (SPEC1 4.12).

Aqui no se decide nada del dominio: que capitulos cambian lo dice la orden del
editor, y lo que ve cada version lo deduce el almacen de dos numeros por fila.
Lo que se decide aqui es el orden de las cosas y que publicar pase por un solo
sitio.
"""

from novela.almacen import Almacen
from novela.nucleo.caminante import IndiceDeLaObra


def rehacer_desde(
    almacen: Almacen,
    indice: IndiceDeLaObra | None,
    id_obra: str,
    desde: int,
    hasta: int,
) -> int:
    """Abre la version siguiente, que reescribe de `desde` a `hasta` (RF-111).

    La version anterior conserva su mundo; la nueva comparte los capitulos
    anteriores a `desde`. Lo relevado sale del indice, para que la produccion
    de la nueva no recupere como eco lo que ya no es suyo. Arrancar la
    produccion es cosa de quien llama, por el camino de siempre (RF-91).
    """
    if not 1 <= desde <= hasta:
        raise ValueError(f"el capitulo {desde} no esta entre 1 y {hasta}")
    nueva = almacen.abrir_version(id_obra, desde, hasta)
    if indice is not None:
        indice.retirar_desde(id_obra, desde)
    return nueva


def publicar(almacen: Almacen, id_obra: str, numero: int) -> str:
    """El unico sitio por el que una version queda publicada (RF-116, D-43).

    Terminar no publica: esto es una orden. Cualquier comprobacion que haya que
    pasar antes de publicar entra aqui y en ningun otro sitio. Devuelve cuando
    quedo publicada.
    """
    return almacen.publicar_version(id_obra, numero)


def de_referencia(almacen: Almacen, id_obra: str) -> int:
    """La que se sirve sin pedir version: la publicada, y si no, la ultima (D-43)."""
    publicada = almacen.version_publicada(id_obra)
    return publicada if publicada is not None else almacen.version_en_curso(id_obra)
