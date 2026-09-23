"""Migraciones numeradas desde el primer dia.

Cada migracion es un numero, un nombre y las sentencias que aplica. No se
reutiliza un numero ni se reescribe una migracion ya aplicada: cambiar el
esquema es anadir la siguiente.
"""

import sqlite3
from collections.abc import Callable

from novela.almacen import esquema
from novela.almacen.conexion import escritura
from novela.almacen.indice import sentencias_del_indice

Migracion = tuple[int, str, Callable[[], list[str]]]

MIGRACIONES: tuple[Migracion, ...] = (
    (1, "esquema inicial de las tres capas y la traza", esquema.sentencias_iniciales),
    (2, "indice hibrido: fragmentos, palabra exacta y huellas", sentencias_del_indice),
    (3, "Recuerdo: lo que el destinatario aporta de su vida", esquema.sentencias_del_recuerdo),
    (4, "Mencion: en que capitulos se usa cada hecho", esquema.sentencias_de_la_mencion),
    (5, "entrevista: el espacio anterior a la obra", esquema.sentencias_de_la_entrevista),
    # Va la ultima de las tres a proposito: es la unica que recorre todas las
    # tablas de artefactos, asi que tiene que correr cuando ya estan todas.
    (
        6,
        "punto de guardado: constancia de auditoria y marca de caducado en lo inmutable",
        esquema.sentencias_del_punto_de_guardado,
    ),
)


def ultima_aplicada(conexion: sqlite3.Connection) -> int:
    hay_tabla = conexion.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'migracion'"
    ).fetchone()
    if not hay_tabla:
        return 0
    fila = conexion.execute(
        "SELECT COALESCE(MAX(numero), 0) AS ultima FROM migracion"
    ).fetchone()
    return int(fila["ultima"])


def aplicar(conexion: sqlite3.Connection) -> int:
    """Aplica lo que falte y devuelve el numero de la ultima migracion."""
    from novela.almacen.artefactos import ahora

    aplicada = ultima_aplicada(conexion)
    for numero, nombre, sentencias in MIGRACIONES:
        if numero <= aplicada:
            continue
        with escritura(conexion):
            for sentencia in sentencias():
                conexion.execute(sentencia)
            conexion.execute(
                "INSERT INTO migracion (numero, nombre, aplicada_en) VALUES (?, ?, ?)",
                (numero, nombre, ahora()),
            )
        aplicada = numero
    return aplicada
