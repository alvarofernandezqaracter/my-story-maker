"""Leer el guion y expandirlo en encargos.

El guion vive en `guion.toml`, al lado de este fichero, y es un artefacto
declarativo: aqui no se decide nada, solo se lee. Expandir un paso es traducir
su concurrencia a la lista de encargos concretos que hay que repartir en
tandas: uno solo, uno por escena, o uno por dimension y escena.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from novela.ajustes import tope_de_ventana
from novela.vocabularios import TAREA_DE_ROL

RUTA_DEL_GUION = Path(__file__).parent / "guion.toml"


@dataclass(frozen=True)
class Contrato:
    """Una dimension de calidad y el rol al que le toca comprobarla."""

    dimension: str
    rol: str


@dataclass(frozen=True)
class Paso:
    """Un paso del guion, tal como esta escrito."""

    numero: int
    tarea: str
    concurrencia: str
    unidad: str
    proyeccion: tuple[str, ...]
    rol: str | None = None
    criba: str | None = None
    vuelve_al_paso: int | None = None
    cuando: str = ""


@dataclass(frozen=True)
class Encargo:
    """Una tarea concreta, lista para mandarse a un rol.

    Es la unidad que se reparte en tandas y la que paga en el techo: su
    proyeccion ocupa el tope de ventana de su rol mientras este abierta.
    """

    paso: int
    tarea: str
    rol: str
    unidad: str
    proyeccion: tuple[str, ...]
    id_obra: str = ""
    capitulo: int | None = None
    escena: str | None = None
    dimension: str | None = None

    @property
    def tope_de_ventana(self) -> int:
        return tope_de_ventana(self.rol)


def _leer() -> dict[str, Any]:
    return tomllib.loads(RUTA_DEL_GUION.read_text(encoding="utf-8"))


def _a_paso(bruto: dict[str, Any]) -> Paso:
    return Paso(
        numero=bruto.get("numero", 0),
        tarea=bruto["tarea"],
        concurrencia=bruto["concurrencia"],
        unidad=bruto["unidad"],
        proyeccion=tuple(bruto["proyeccion"]),
        rol=bruto.get("rol"),
        criba=bruto.get("criba"),
        vuelve_al_paso=bruto.get("vuelve_al_paso"),
        cuando=bruto.get("cuando", ""),
    )


_BRUTO = _leer()

VERSION: int = _BRUTO["version"]

PASOS: tuple[Paso, ...] = tuple(_a_paso(p) for p in _BRUTO["paso"])

FUERA_DEL_GUION: dict[str, Paso] = {
    nombre: _a_paso(bruto) for nombre, bruto in _BRUTO["fuera_del_guion"].items()
}

CRIBAS: dict[str, tuple[Contrato, ...]] = {
    nombre: tuple(Contrato(c["dimension"], c["rol"]) for c in contratos)
    for nombre, contratos in _BRUTO["criba"].items()
}


def paso(numero: int) -> Paso:
    for candidato in PASOS:
        if candidato.numero == numero:
            return candidato
    raise KeyError(f"el guion no tiene paso {numero}")


def expandir(
    paso_del_guion: Paso,
    *,
    id_obra: str = "",
    capitulo: int | None = None,
    escenas: tuple[str, ...] = (),
) -> list[Encargo]:
    """Traduce un paso a los encargos concretos que hay que mandar.

    La concurrencia declarada es lo unico que decide cuantos salen: ni el paso
    ni ningun agente eligen abanico.
    """
    if paso_del_guion.concurrencia == "solo":
        rol = paso_del_guion.rol
        if rol is None:
            raise ValueError(f"el paso {paso_del_guion.numero} va solo pero no declara rol")
        return [
            Encargo(
                paso=paso_del_guion.numero,
                tarea=paso_del_guion.tarea,
                rol=rol,
                unidad=paso_del_guion.unidad,
                proyeccion=paso_del_guion.proyeccion,
                id_obra=id_obra,
                capitulo=capitulo,
            )
        ]

    if paso_del_guion.concurrencia == "por_escena":
        rol = paso_del_guion.rol
        if rol is None:
            raise ValueError(f"el paso {paso_del_guion.numero} no declara rol")
        return [
            Encargo(
                paso=paso_del_guion.numero,
                tarea=paso_del_guion.tarea,
                rol=rol,
                unidad=paso_del_guion.unidad,
                proyeccion=paso_del_guion.proyeccion,
                id_obra=id_obra,
                capitulo=capitulo,
                escena=escena,
            )
            for escena in escenas
        ]

    if paso_del_guion.concurrencia == "por_dimension_y_escena":
        if paso_del_guion.criba is None:
            raise ValueError(f"el paso {paso_del_guion.numero} criba sin declarar criba")
        return [
            Encargo(
                paso=paso_del_guion.numero,
                tarea=TAREA_DE_ROL[contrato.rol],
                rol=contrato.rol,
                unidad=paso_del_guion.unidad,
                proyeccion=paso_del_guion.proyeccion,
                id_obra=id_obra,
                capitulo=capitulo,
                escena=escena,
                dimension=contrato.dimension,
            )
            for escena in escenas
            for contrato in CRIBAS[paso_del_guion.criba]
        ]

    raise ValueError(f"concurrencia desconocida: {paso_del_guion.concurrencia!r}")
