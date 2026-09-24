"""Los briefs de prueba, cargados y validados sin gastar (SPEC1 RF-201).

Metodo: `prueba`. Ninguno se lanza: se comprueba que cada uno lo aceptaria
`POST /obras`, que lo que espera de cada comprobacion nombra comprobaciones que
existen y que los dos adversarios estan armados como dicen. Correrlos es la
segunda mitad de la tarea. Ningun recuento se clava: todo se lee de los
vocabularios y de los propios ficheros.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from novela import juez_de_la_novela as juez
from novela.almacen import Almacen
from novela.api.modelos import Brief
from novela.vocabularios import (
    CRITERIO_DEL_JUEZ_DE_LA_NOVELA,
    GANCHOS,
    PROPOSITO_DEL_BRIEF_DE_PRUEBA,
    RESULTADO_ESPERADO,
    VALIDADOR_DE_LA_PUERTA,
)

CARPETA = Path(__file__).resolve().parent.parent / "briefs-de-prueba"
FICHEROS = sorted(CARPETA.glob("*.json"))

COMPROBACIONES = {
    **{f"puerta.{v}": ("pasa", "falla", "puede_fallar") for v in VALIDADOR_DE_LA_PUERTA},
    **{f"gancho.{g}": ("pasa", "falla", "puede_fallar") for g in GANCHOS},
    **{f"juez.{c}": ("se_puntua", "no_se_puntua") for c in CRITERIO_DEL_JUEZ_DE_LA_NOVELA},
}


def _leer(fichero: Path) -> dict[str, Any]:
    return dict(json.loads(fichero.read_text(encoding="utf-8")))


def _por_proposito(proposito: str) -> list[dict[str, Any]]:
    return [b for b in map(_leer, FICHEROS) if b["proposito"] == proposito]


def _esperado(brief: dict[str, Any]) -> dict[str, str]:
    return {e["comprobacion"]: e["resultado"] for e in brief["se_espera"]}


def test_hay_al_menos_un_brief_de_cada_proposito() -> None:
    propositos = {_leer(f)["proposito"] for f in FICHEROS}
    assert propositos >= set(PROPOSITO_DEL_BRIEF_DE_PRUEBA)
    assert propositos <= set(PROPOSITO_DEL_BRIEF_DE_PRUEBA)


@pytest.mark.parametrize("fichero", FICHEROS, ids=lambda f: f.stem)
def test_cada_brief_lo_aceptaria_post_obras(fichero: Path) -> None:
    datos = _leer(fichero)
    assert set(datos) == {"proposito", "para_que", "se_espera", "brief"}
    assert datos["para_que"].strip()
    Brief.model_validate(datos["brief"])


@pytest.mark.parametrize("fichero", FICHEROS, ids=lambda f: f.stem)
def test_cada_brief_dice_que_espera_de_cada_comprobacion(fichero: Path) -> None:
    datos = _leer(fichero)
    vistas = [e["comprobacion"] for e in datos["se_espera"]]
    assert sorted(vistas) == sorted(COMPROBACIONES), "falta o sobra alguna comprobacion"
    for entrada in datos["se_espera"]:
        assert entrada["resultado"] in RESULTADO_ESPERADO
        assert entrada["resultado"] in COMPROBACIONES[entrada["comprobacion"]], entrada
        assert entrada["por_que"].strip()


@pytest.mark.parametrize("fichero", FICHEROS, ids=lambda f: f.stem)
def test_lo_que_espera_del_juez_es_lo_que_el_juez_puntuara(fichero: Path) -> None:
    datos = _leer(fichero)
    se_puntuan = juez.criterios_que_se_puntuan(datos["brief"])
    for criterio in CRITERIO_DEL_JUEZ_DE_LA_NOVELA:
        esperado = "se_puntua" if criterio in se_puntuan else "no_se_puntua"
        assert _esperado(datos)[f"juez.{criterio}"] == esperado


def test_la_incoherencia_temporal_solo_la_ve_lean() -> None:
    for datos in _por_proposito("incoherencia_temporal"):
        esperado = _esperado(datos)
        assert esperado["puerta.cronologia"] == "falla"
        otros = [v for v in VALIDADOR_DE_LA_PUERTA if v != "cronologia"]
        assert {esperado[f"puerta.{v}"] for v in otros} == {"pasa"}
        # Dos sucesos del mismo dia exacto: es lo que `un_solo_lugar` mira.
        assert "12 de marzo de 1605" in datos["brief"]["premisa"]
        assert "día exacto" in datos["brief"]["politicas_globales"]["fechas"]


def test_la_inyeccion_manda_ordenes_que_un_guardarrail_puede_ver(tmp_path: Path) -> None:
    almacen = Almacen(tmp_path / "vetos.sqlite3")
    almacen.migrar()
    globales = almacen.terminos_vetados_globales()
    almacen.cerrar()
    for datos in _por_proposito("inyeccion"):
        destinatario = datos["brief"]["destinatario"]
        escrito = " ".join(
            [destinatario["dedicatoria"], *destinatario["rasgos"], *destinatario["recuerdos"]]
        ).lower()
        # Pide un termino de la lista global, que es lo que `policy` para.
        assert any(termino in escrito for termino in globales)
        # E intenta cerrar la marca de los datos del encargo.
        assert "</datos_del_encargo>" in escrito
        assert _esperado(datos)["gancho.policy"] == "puede_fallar"
