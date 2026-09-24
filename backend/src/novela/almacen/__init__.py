"""`almacen/`: la unica puerta de lectura y escritura de la persistencia.

Nadie mas abre la base de datos. Quien necesite un artefacto lo pide aqui por
su nombre de dominio; quien produzca uno lo entrega aqui. Esto es lo que hace
que el almacen tenga un solo lector y un solo escritor, y lo que permite
cambiar su forma fisica sin tocar diez carpetas.
"""

from novela.almacen.artefactos import (
    Almacen,
    Artefacto,
    ArtefactoRechazado,
    EscrituraProhibida,
    VersionNoAdmitida,
    abrir_almacen,
    ahora,
    cuerpos,
    nuevo_id,
)

__all__ = [
    "Almacen",
    "Artefacto",
    "ArtefactoRechazado",
    "EscrituraProhibida",
    "VersionNoAdmitida",
    "abrir_almacen",
    "ahora",
    "cuerpos",
    "nuevo_id",
]
