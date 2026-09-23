"""`tareas/`: una carpeta por tipo de tarea del censo.

Cada carpeta lleva todo lo suyo dentro —su contrato, su prompt, el esquema del
artefacto que escribe y lo que rechaza de lo que recibe— de modo que la regla
«un rol, una tarea» queda visible en el arbol de ficheros: declarar un rol nuevo
es anadir una carpeta.

**Las carpetas no se importan entre si.** Se comunican por artefactos, a traves
de `almacen/`. Entre dos tareas se duplica antes que acoplarse.

Lo que hay aqui es el catalogo: quien lee esas carpetas y se las sirve a quien
reparte los turnos. Es entrada versionada con el repositorio, no
almacenamiento: el sistema la lee y nunca la escribe.
"""

import tomllib
from functools import cache
from pathlib import Path
from typing import Any

CARPETA = Path(__file__).parent


@cache
def contrato_de_tarea(tarea: str) -> dict[str, Any]:
    ruta = CARPETA / tarea / "contrato.toml"
    if not ruta.exists():
        raise KeyError(f"la tarea {tarea!r} no tiene carpeta con contrato")
    return tomllib.loads(ruta.read_text(encoding="utf-8"))


@cache
def contrato_de_verificacion(tarea: str, dimension: str) -> dict[str, Any]:
    ruta = CARPETA / tarea / "contratos" / f"{dimension}.toml"
    if not ruta.exists():
        raise KeyError(f"{tarea} no tiene contrato para la dimension {dimension!r}")
    return tomllib.loads(ruta.read_text(encoding="utf-8"))


@cache
def prompt_de_tarea(tarea: str) -> str:
    return (CARPETA / tarea / "prompt.md").read_text(encoding="utf-8")


@cache
def esquema_de_tarea(tarea: str) -> str:
    return (CARPETA / tarea / "esquema.json").read_text(encoding="utf-8")


def tareas_declaradas() -> list[str]:
    """Las carpetas que hay. Se enumeran contra el censo, no se suponen."""
    return sorted(
        hija.name
        for hija in CARPETA.iterdir()
        if hija.is_dir() and (hija / "contrato.toml").exists()
    )


def dimensiones_de(tarea: str) -> list[str]:
    carpeta = CARPETA / tarea / "contratos"
    if not carpeta.exists():
        return []
    return sorted(fichero.stem for fichero in carpeta.glob("*.toml"))


class CatalogoDelRepositorio:
    """Sirve el contrato, la proyeccion minima, el prompt y el esquema.

    Es lo que se le pasa al que camina el guion y al ejecutor: ni uno ni otro
    conocen la forma de estas carpetas.
    """

    def contrato(self, tarea: str, dimension: str | None) -> dict[str, Any] | None:
        if dimension is None:
            return None
        bruto = contrato_de_verificacion(tarea, dimension)
        critica = bruto.get("critica", {})
        return {
            "dimension": bruto["dimension"],
            "predicado": bruto["predicado"],
            "metodo_de_verificacion": bruto["metodo_de_verificacion"],
            "alcance": bruto["alcance"],
            "severidad": critica.get("severidad"),
            "evidencia_aceptada": critica.get("evidencia_aceptada"),
            **({"rubrica": critica["rubrica"]} if "rubrica" in critica else {}),
            **({"ruidosa": critica["ruidosa"]} if "ruidosa" in critica else {}),
        }

    def proyeccion_minima(self, tarea: str, dimension: str | None) -> tuple[str, ...]:
        if dimension is None:
            return ()
        return tuple(contrato_de_verificacion(tarea, dimension)["proyeccion_minima"])

    def prompt(self, tarea: str, dimension: str | None) -> str:
        return prompt_de_tarea(tarea)

    def esquema(self, tarea: str) -> str:
        return esquema_de_tarea(tarea)

    def escribe(self, tarea: str) -> tuple[str, ...]:
        return tuple(contrato_de_tarea(tarea)["escribe"])

    def rechaza(self, tarea: str) -> dict[str, list[str]]:
        return contrato_de_tarea(tarea).get("rechaza", {})
