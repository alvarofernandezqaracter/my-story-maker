"""Como se abre la base y como se escribe en ella.

Un solo escritor serializado y lecturas aparte que no lo bloquean. La linea de
partida de toda conexion es la misma: WAL, espera explicita por bloqueo,
`foreign_keys` encendidas —en SQLite vienen apagadas— y `synchronous = NORMAL`,
que es lo que WAL permite sin arriesgar la durabilidad que aqui importa.

Las escrituras empiezan en `BEGIN IMMEDIATE`. Empezar en modo diferido y
ascender a escritura a mitad es la receta del bloqueo que no se reproduce en
local.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from novela.ajustes import ESPERA_POR_BLOQUEO_MS


def abrir(ruta: Path | str, *, solo_lectura: bool = False) -> sqlite3.Connection:
    """Abre la base con la linea de partida del proyecto.

    `solo_lectura` da una conexion de lectura: la usa la API para servir lo
    producido sin estorbar a la produccion.
    """
    if solo_lectura:
        conexion = sqlite3.connect(
            f"file:{Path(ruta).as_posix()}?mode=ro",
            uri=True,
            isolation_level=None,
            check_same_thread=False,
        )
    else:
        conexion = sqlite3.connect(
            str(ruta),
            isolation_level=None,
            check_same_thread=False,
        )
        conexion.execute("PRAGMA journal_mode = WAL")
        conexion.execute("PRAGMA synchronous = NORMAL")
    conexion.execute(f"PRAGMA busy_timeout = {ESPERA_POR_BLOQUEO_MS}")
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.row_factory = sqlite3.Row
    _cargar_sqlite_vec(conexion)
    return conexion


def _cargar_sqlite_vec(conexion: sqlite3.Connection) -> None:
    """La extension vectorial se carga en toda conexion: el indice esta detras
    de la misma puerta que el resto del almacen."""
    import sqlite_vec

    conexion.enable_load_extension(True)
    sqlite_vec.load(conexion)
    conexion.enable_load_extension(False)


@contextmanager
def escritura(conexion: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Una transaccion de escritura: se escribe la unidad entera o nada.

    Es lo que sostiene RNF-06: un corte a mitad no deja artefactos a medias ni
    estados materializados inconsistentes.
    """
    conexion.execute("BEGIN IMMEDIATE")
    try:
        yield conexion
    except BaseException:
        conexion.execute("ROLLBACK")
        raise
    conexion.execute("COMMIT")
