"""El lanzador de los briefs de prueba, sin gastar un euro.

Cierre por `prueba` de RF-203. Lo que se comprueba sin lanzar ninguna obra: que
no se corre nada sin pedirlo, que los cinco briefs se cargan en orden estable,
que lo que devuelven la puerta, los ganchos y el juez se traduce a las mismas
claves que los briefs declaran en `se_espera`, y que la tabla marca lo que no
cuadra. Lo que de verdad gasta —producir cinco novelas— es la corrida, y no la
lanza ninguna prueba.
"""

from typing import Any

import pytest

from novela import lanzador_de_briefs as lanzador
from novela.vocabularios import (
    CRITERIO_DEL_JUEZ_DE_LA_NOVELA,
    GANCHOS,
    VALIDADOR_DE_LA_PUERTA,
)


class AlmacenFingido:
    """Solo lo que el lanzador le pide: las trazas de una obra."""

    def __init__(self, trazas: list[Any]) -> None:
        self._trazas = trazas

    def listar_trazas(self, id_obra: str, **_: Any) -> list[Any]:
        return self._trazas


class TrazaFingida:
    def __init__(self, ganchos: dict[str, Any] | None) -> None:
        self.cuerpo: dict[str, Any] = {"ganchos": ganchos}


# --- Nada se corre sin pedirlo --------------------------------------------


def test_sin_permiso_no_corre_nada(capsys: pytest.CaptureFixture[str]) -> None:
    """Cada brief lanza una obra de verdad: hay que confirmarlo."""
    codigo = lanzador.main([])

    assert codigo == 1
    assert "--si-gasto" in capsys.readouterr().out


def test_un_brief_que_no_existe_se_dice_y_no_corre(
    capsys: pytest.CaptureFixture[str],
) -> None:
    codigo = lanzador.main(["--solo", "no-existe", "--si-gasto"])

    assert codigo == 2
    assert "no-existe" in capsys.readouterr().out


# --- Los briefs de RF-201 se cargan ---------------------------------------


def test_se_cargan_los_cinco_briefs_en_orden_estable() -> None:
    """El orden es el del nombre: la tabla tiene que salir igual cada vez."""
    nombres = [nombre for nombre, _ in lanzador.cargar_briefs()]

    assert nombres == sorted(nombres)
    assert len(nombres) == 5


def test_toda_comprobacion_declarada_la_sabe_observar_el_lanzador() -> None:
    """Si un brief nombra algo que el lanzador no mira, la tabla mentiría."""
    declaradas = {
        e["comprobacion"]
        for _, brief in lanzador.cargar_briefs()
        for e in brief["se_espera"]
    }
    observables = (
        {f"puerta.{v}" for v in VALIDADOR_DE_LA_PUERTA}
        | {f"gancho.{g}" for g in GANCHOS}
        | {f"juez.{c}" for c in CRITERIO_DEL_JUEZ_DE_LA_NOVELA}
    )

    assert declaradas <= observables, declaradas - observables


# --- De lo que devuelve cada pieza a las claves de `se_espera` -------------


def test_la_puerta_sin_fallos_deja_todos_sus_validadores_en_pasa() -> None:
    observado = lanzador._de_la_puerta({"fallos": []})

    assert observado == {f"puerta.{v}": "pasa" for v in VALIDADOR_DE_LA_PUERTA}


def test_el_validador_que_fallo_sale_como_falla_y_los_demas_no() -> None:
    """La puerta solo enumera lo que falló: lo demás pasó."""
    observado = lanzador._de_la_puerta(
        {"fallos": [{"validador": "cronologia", "capitulo": 2, "detalle": "dos lugares"}]}
    )

    assert observado["puerta.cronologia"] == "falla"
    assert observado["puerta.esquema"] == "pasa"


def test_un_gancho_que_bloqueo_en_algun_intento_sale_como_falla() -> None:
    almacen = AlmacenFingido(
        [
            TrazaFingida(None),
            TrazaFingida({"final": [{"gancho": "policy", "pasa": False}]}),
            TrazaFingida({"final": [{"gancho": "policy", "pasa": True}]}),
        ]
    )

    observado = lanzador._de_los_ganchos(almacen, "obr_1")  # type: ignore[arg-type]

    assert observado["gancho.policy"] == "falla"
    assert observado["gancho.validar_capitulo"] == "pasa"


def test_un_criterio_que_el_juez_no_puntuo_sale_como_no_se_puntua() -> None:
    """Sin destinatario, la personalización no se puntúa: no es un fallo."""
    observado, notas = lanzador._del_juez(
        [
            {"criterio": "funciona_como_novela", "nota": 4},
            {"criterio": "fidelidad_a_la_epoca", "nota": 5},
        ]
    )

    assert observado["juez.personalizacion_integrada"] == "no_se_puntua"
    assert observado["juez.funciona_como_novela"] == "se_puntua"
    assert notas == {"juez.funciona_como_novela": 4, "juez.fidelidad_a_la_epoca": 5}


# --- La tabla ---------------------------------------------------------------


def test_puede_fallar_cuadra_con_cualquiera_de_los_dos() -> None:
    """Es una expectativa, no un resultado: el brief admite las dos."""
    assert lanzador.Comprobacion("puerta.nombres", "puede_fallar", "pasa").cuadra
    assert lanzador.Comprobacion("puerta.nombres", "puede_fallar", "falla").cuadra
    assert not lanzador.Comprobacion("puerta.nombres", "pasa", "falla").cuadra


def test_la_tabla_marca_lo_que_no_cuadra() -> None:
    corrida = lanzador.Corrida(brief="normal", proposito="normal")
    corrida.comprobaciones = [
        lanzador.Comprobacion("puerta.esquema", "pasa", "pasa"),
        lanzador.Comprobacion("puerta.cronologia", "pasa", "falla"),
    ]

    texto = lanzador.tabla([corrida])

    assert "**no**" in texto
    assert not corrida.cuadra_todo


def test_un_brief_que_reventó_sale_en_la_tabla_con_su_motivo() -> None:
    """Que una corrida se caiga no puede dejar la tabla sin esa fila."""
    corrida = lanzador.Corrida(brief="inyeccion", proposito="inyeccion")
    corrida.fallo = "RubricaNoDisponible: falta la rubrica"

    texto = lanzador.tabla([corrida])

    assert "inyeccion" in texto
    assert "RubricaNoDisponible" in texto
    assert not corrida.cuadra_todo
