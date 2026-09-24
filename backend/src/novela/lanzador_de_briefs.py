"""Corre los briefs de prueba de uno en uno y contrasta lo que se esperaba.

Es la segunda mitad de §4.21: los briefs ya estan escritos y validados sin
gastar (RF-201); esto los ejecuta de verdad y deja la tabla de que comprobacion
paso y cual fallo en cada uno.

**De uno en uno, y no por prudencia.** El juez de la novela no se lanza si hay
produccion en marcha en la instalacion (RF-197), asi que dos briefs a la vez
dejarian sin juzgar al segundo. Cada brief se lleva hasta el final —producir,
pasar la puerta, publicar y juzgar— antes de empezar el siguiente.

**Esto gasta.** Cada brief lanza una obra entera con agentes de verdad. Por eso
no se ejecuta al importarlo ni desde ninguna prueba: hay que pedirlo por su
nombre y confirmarlo con `--si-gasto`.
"""

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from novela import juez_de_la_novela
from novela.almacen import Almacen
from novela.api.aplicacion import Produccion, _alta
from novela.api.modelos import Brief
from novela.nucleo import versiones
from novela.vocabularios import (
    CRITERIO_DEL_JUEZ_DE_LA_NOVELA,
    GANCHOS,
    VALIDADOR_DE_LA_PUERTA,
)

CARPETA_DE_LOS_BRIEFS = Path(__file__).resolve().parents[2] / "briefs-de-prueba"

# Lo que se puede observar de cada comprobacion al correr un brief. Sale del
# vocabulario `resultado_esperado` de RF-201: `puede_fallar` es una expectativa,
# no un resultado, asi que nunca se observa.
PASA, FALLA, SE_PUNTUA, NO_SE_PUNTUA = "pasa", "falla", "se_puntua", "no_se_puntua"


@dataclass
class Comprobacion:
    """Una linea de la tabla: que se esperaba y que salio."""

    comprobacion: str
    esperado: str
    obtenido: str
    por_que: str = ""

    @property
    def cuadra(self) -> bool:
        if self.esperado == "puede_fallar":
            return self.obtenido in {PASA, FALLA}
        return self.esperado == self.obtenido


@dataclass
class Corrida:
    """Lo que dio un brief de principio a fin."""

    brief: str
    proposito: str
    id_obra: str = ""
    publicada: bool = False
    comprobaciones: list[Comprobacion] = field(default_factory=list)
    notas: dict[str, int] = field(default_factory=dict)
    segundos: float = 0.0
    fallo: str = ""

    @property
    def cuadra_todo(self) -> bool:
        return not self.fallo and all(c.cuadra for c in self.comprobaciones)


def cargar_briefs(carpeta: Path = CARPETA_DE_LOS_BRIEFS) -> list[tuple[str, dict[str, Any]]]:
    """Los briefs de prueba, en orden de nombre para que la tabla sea estable."""
    return [
        (ruta.stem, json.loads(ruta.read_text(encoding="utf-8")))
        for ruta in sorted(carpeta.glob("*.json"))
    ]


def _lo_esperado(declarado: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    return {e["comprobacion"]: (e["resultado"], e.get("por_que", "")) for e in declarado}


def _de_la_puerta(resultado: dict[str, Any]) -> dict[str, str]:
    """De lo que devuelve la puerta a `puerta.<validador>` con su resultado.

    La puerta solo enumera lo que fallo, asi que los validadores se recorren del
    vocabulario: lo que no aparece entre los fallos es que paso.
    """
    fallados = {str(f.get("validador")) for f in resultado.get("fallos", [])}
    return {
        f"puerta.{v}": (FALLA if v in fallados else PASA) for v in VALIDADOR_DE_LA_PUERTA
    }


def _de_los_ganchos(almacen: Almacen, id_obra: str) -> dict[str, str]:
    """De las trazas de la obra a `gancho.<gancho>` con su resultado.

    Un gancho falla en la obra si su veredicto final no paso en algun intento:
    lo que la tabla dice es si ese brief lo hizo saltar, no cuantas veces.
    """
    fallados: set[str] = set()
    for traza in almacen.listar_trazas(id_obra):
        registro = traza.cuerpo.get("ganchos") or {}
        for veredicto in registro.get("final", ()):
            if not veredicto.get("pasa", True):
                fallados.add(str(veredicto.get("gancho")))
    return {f"gancho.{g}": (FALLA if g in fallados else PASA) for g in GANCHOS}


def _del_juez(veredicto: Any) -> tuple[dict[str, str], dict[str, int]]:
    """De lo que devuelve el juez a `juez.<criterio>` y a sus notas."""
    puntuados = {c["criterio"]: int(c["nota"]) for c in veredicto}
    observado = {
        f"juez.{criterio}": (SE_PUNTUA if criterio in puntuados else NO_SE_PUNTUA)
        for criterio in CRITERIO_DEL_JUEZ_DE_LA_NOVELA
    }
    return observado, {f"juez.{k}": v for k, v in puntuados.items()}


def correr_uno(casa: Produccion, nombre: str, contenido: dict[str, Any]) -> Corrida:
    """Un brief entero: producir, pasar la puerta, publicar y juzgar."""
    corrida = Corrida(brief=nombre, proposito=contenido["proposito"])
    esperado = _lo_esperado(contenido["se_espera"])
    arranque = time.monotonic()
    try:
        brief = Brief.model_validate(contenido["brief"])
        corrida.id_obra = casa.almacen.crear_obra(*_alta(brief))
        casa.arrancar(corrida.id_obra, brief.capitulos_objetivo)
        casa.hilos[corrida.id_obra].join()

        observado: dict[str, str] = {}
        try:
            versiones.publicar(
                casa.almacen, corrida.id_obra, 1, casa.catalogo, casa.demostrador
            )
            corrida.publicada = True
            observado |= _de_la_puerta(
                versiones.puerta(
                    casa.almacen, corrida.id_obra, 1, casa.catalogo, casa.demostrador
                )
            )
        except versiones.PuertaNoSuperada as rechazo:
            observado |= _de_la_puerta(rechazo.resultado)

        observado |= _de_los_ganchos(casa.almacen, corrida.id_obra)

        juicio = juez_de_la_novela.juzgar_version(
            casa.almacen, corrida.id_obra, 1, observabilidad=casa.observabilidad
        )
        del_juez, corrida.notas = _del_juez(juicio.notas)
        observado |= del_juez

        corrida.comprobaciones = [
            Comprobacion(clave, esperado[clave][0], observado.get(clave, "no observado"),
                         esperado[clave][1])
            for clave in sorted(esperado)
        ]
    except Exception as error:  # noqa: BLE001
        corrida.fallo = f"{type(error).__name__}: {error}"
    corrida.segundos = time.monotonic() - arranque
    return corrida


def correr_todos(casa: Produccion, briefs: list[tuple[str, dict[str, Any]]]) -> list[Corrida]:
    """Uno detras de otro. Nunca dos a la vez: el juez no se lanzaria."""
    corridas = []
    for numero, (nombre, contenido) in enumerate(briefs, start=1):
        print(f"[{numero}/{len(briefs)}] {nombre} ({contenido['proposito']})...", flush=True)
        corrida = correr_uno(casa, nombre, contenido)
        estado = "cuadra" if corrida.cuadra_todo else (corrida.fallo or "hay diferencias")
        print(f"    {int(corrida.segundos)} s · {estado}", flush=True)
        corridas.append(corrida)
    return corridas


def tabla(corridas: list[Corrida]) -> str:
    """La tabla que pide la rubrica: que comprobacion paso en cada brief."""
    lineas = [
        "| Brief | Propósito | Comprobación | Esperado | Obtenido | ¿Cuadra? |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in corridas:
        if c.fallo:
            lineas.append(f"| {c.brief} | {c.proposito} | — | — | {c.fallo} | no |")
            continue
        for comp in c.comprobaciones:
            lineas.append(
                f"| {c.brief} | {c.proposito} | `{comp.comprobacion}` | {comp.esperado} "
                f"| {comp.obtenido} | {'sí' if comp.cuadra else '**no**'} |"
            )
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    partes = argparse.ArgumentParser(description=__doc__)
    partes.add_argument("--si-gasto", action="store_true",
                        help="confirma que se lanzan obras de verdad, con su coste")
    partes.add_argument("--solo", default="", help="corre solo el brief con ese nombre")
    partes.add_argument("--salida", type=Path, default=None,
                        help="fichero donde escribir la tabla")
    opciones = partes.parse_args(argv)

    briefs = cargar_briefs()
    if opciones.solo:
        briefs = [b for b in briefs if b[0] == opciones.solo]
        if not briefs:
            print(f"no hay ningun brief que se llame {opciones.solo!r}")
            return 2
    if not opciones.si_gasto:
        print(f"{len(briefs)} briefs. Correrlos lanza {len(briefs)} obras de verdad y "
              "cuesta dinero.\nSi es lo que quieres, vuelve a lanzarlo con --si-gasto.")
        return 1

    casa = Produccion()
    try:
        corridas = correr_todos(casa, briefs)
    finally:
        casa.cerrar()

    texto = tabla(corridas)
    print("\n" + texto)
    if opciones.salida:
        opciones.salida.write_text(texto + "\n", encoding="utf-8")
        print(f"\nescrita en {opciones.salida}")
    return 0 if all(c.cuadra_todo for c in corridas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
