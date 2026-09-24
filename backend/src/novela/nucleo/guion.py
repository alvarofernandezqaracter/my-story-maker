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
from novela.vocabularios import AL_AGOTARSE, GANCHOS, TAREA_DE_ROL

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
    reintentos: int
    al_agotarse: str
    rol: str | None = None
    criba: str | None = None
    vuelve_al_paso: int | None = None
    cuando: str = ""
    ganchos: tuple[str, ...] = ()
    reserva_de_la_vuelta: int = 0


@dataclass(frozen=True)
class Encargo:
    """Una tarea concreta, lista para mandarse a un rol.

    Es la unidad que se reparte en tandas y la que paga en el techo: su
    proyeccion ocupa el tope de ventana de su rol mientras este abierta.

    `reintentos` y `al_agotarse` los copia siempre el guion desde el paso que
    lo expande. El valor por defecto es el mas prudente —un intento y detener—
    y solo lo usan los encargos que las pruebas fabrican a mano.
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
    reintentos: int = 1
    al_agotarse: str = "detener_obra"
    # Los hooks de su subagente y lo que cuesta de entrada su vuelta de
    # correccion (SPEC1 4.13). Los copia el guion desde el paso.
    ganchos: tuple[str, ...] = ()
    reserva_de_la_vuelta: int = 0

    @property
    def tope_de_ventana(self) -> int:
        return tope_de_ventana(self.rol)


def _leer() -> dict[str, Any]:
    return tomllib.loads(RUTA_DEL_GUION.read_text(encoding="utf-8"))


class GuionInvalido(Exception):
    """El guion no declara algo que la pieza que lo camina necesita saber."""


def _politica(bruto: dict[str, Any]) -> tuple[int, str]:
    """El tope y lo que pasa al agotarse estan escritos, o el guion no carga.

    Un paso sin ellos obligaria a improvisar sobre la marcha lo que pasa cuando
    su tarea falla, que es lo que RF-95 prohibe.
    """
    nombre = bruto.get("numero") or bruto.get("tarea")
    if "reintentos" not in bruto or "al_agotarse" not in bruto:
        raise GuionInvalido(f"el paso {nombre} no declara `reintentos` y `al_agotarse`")
    reintentos = bruto["reintentos"]
    if not isinstance(reintentos, int) or isinstance(reintentos, bool) or reintentos < 1:
        raise GuionInvalido(f"el paso {nombre} declara {reintentos!r} intentos")
    if bruto["al_agotarse"] not in AL_AGOTARSE:
        raise GuionInvalido(
            f"el paso {nombre}: {bruto['al_agotarse']!r} no esta en `al_agotarse`"
        )
    return reintentos, bruto["al_agotarse"]


def _ganchos(bruto: dict[str, Any]) -> tuple[tuple[str, ...], int]:
    """Los hooks del paso, de un vocabulario cerrado, y su reserva (RF-120).

    Un paso con hooks y sin reserva dejaria sin contar la entrada que cuesta la
    vuelta de correccion, que es lo que RF-128 prohibe.
    """
    nombre = bruto.get("numero") or bruto.get("tarea")
    ganchos = tuple(bruto.get("ganchos", ()))
    desconocidos = [gancho for gancho in ganchos if gancho not in GANCHOS]
    if desconocidos:
        raise GuionInvalido(f"el paso {nombre}: {desconocidos!r} no estan en `ganchos`")
    reserva = bruto.get("reserva_de_la_vuelta", 0)
    if not isinstance(reserva, int) or isinstance(reserva, bool) or reserva < 0:
        raise GuionInvalido(f"el paso {nombre} declara una reserva de {reserva!r}")
    if ganchos and reserva == 0:
        raise GuionInvalido(f"el paso {nombre} lleva ganchos sin `reserva_de_la_vuelta`")
    return ganchos, reserva


def _a_paso(bruto: dict[str, Any]) -> Paso:
    reintentos, al_agotarse = _politica(bruto)
    ganchos, reserva = _ganchos(bruto)
    return Paso(
        numero=bruto.get("numero", 0),
        tarea=bruto["tarea"],
        concurrencia=bruto["concurrencia"],
        unidad=bruto["unidad"],
        proyeccion=tuple(bruto["proyeccion"]),
        reintentos=reintentos,
        al_agotarse=al_agotarse,
        rol=bruto.get("rol"),
        criba=bruto.get("criba"),
        vuelve_al_paso=bruto.get("vuelve_al_paso"),
        cuando=bruto.get("cuando", ""),
        ganchos=ganchos,
        reserva_de_la_vuelta=reserva,
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
                reintentos=paso_del_guion.reintentos,
                al_agotarse=paso_del_guion.al_agotarse,
                ganchos=paso_del_guion.ganchos,
                reserva_de_la_vuelta=paso_del_guion.reserva_de_la_vuelta,
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
                reintentos=paso_del_guion.reintentos,
                al_agotarse=paso_del_guion.al_agotarse,
                ganchos=paso_del_guion.ganchos,
                reserva_de_la_vuelta=paso_del_guion.reserva_de_la_vuelta,
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
                reintentos=paso_del_guion.reintentos,
                al_agotarse=paso_del_guion.al_agotarse,
                ganchos=paso_del_guion.ganchos,
                reserva_de_la_vuelta=paso_del_guion.reserva_de_la_vuelta,
                id_obra=id_obra,
                capitulo=capitulo,
                escena=escena,
                dimension=contrato.dimension,
            )
            for escena in escenas
            for contrato in CRIBAS[paso_del_guion.criba]
        ]

    raise ValueError(f"concurrencia desconocida: {paso_del_guion.concurrencia!r}")
