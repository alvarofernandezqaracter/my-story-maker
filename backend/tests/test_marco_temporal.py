"""El marco temporal del Contable (SPEC1 4.24, RF-210, D-94).

El Contable fechaba sin ancla y se inventaba el ano: 1500 en un capitulo, 1588
en el siguiente. Estas pruebas miran lo que su ventana trae para no tener que
inventarlo, y que del plan no le llega mas que el marco de las escenas.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from novela.almacen import Almacen
from novela.almacen.artefactos import Artefacto, abrir_almacen
from novela.nucleo import guion
from novela.nucleo.proyecciones import ensamblar
from novela.tareas import prompt_de_tarea


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "marco.sqlite3")
    yield almacen
    almacen.cerrar()


def _escena(id_obra: str, capitulo: int, orden: int, instante: str) -> Artefacto:
    return Artefacto(
        "Escena",
        {
            "pov": "per_00000001",
            "elenco_presente": ["per_00000001"],
            "objetivo": "cobrar la deuda",
            "marco": {"lugar": "lug_00000001", "instante": instante, "duracion": "una tarde"},
        },
        id_obra=id_obra,
        capitulo=capitulo,
        orden=orden,
        estado="planificado",
    )


def _ventana_de_plegar(almacen: Almacen, id_obra: str, capitulo: int) -> dict[str, object]:
    encargo = guion.expandir(guion.paso(9), id_obra=id_obra, capitulo=capitulo, escenas=())[0]
    marco = ensamblar(almacen, encargo).materiales["marco_temporal_del_capitulo"]
    assert isinstance(marco, dict)
    return marco


def test_el_capitulo_1_trae_la_epoca_y_el_marco_de_sus_escenas_en_orden(
    almacen: Almacen,
) -> None:
    id_obra = almacen.crear_obra({"titulo": "T", "epoca": "Salamanca, 1584"})
    segunda = almacen.guardar([_escena(id_obra, 1, 2, "1584-10-16")])[0]
    primera = almacen.guardar([_escena(id_obra, 1, 1, "1584-10-15")])[0]
    almacen.guardar([_escena(id_obra, 2, 1, "1584-11-01")])

    marco = _ventana_de_plegar(almacen, id_obra, 1)

    assert marco["epoca"] == "Salamanca, 1584"
    assert marco["fecha_de_cierre_anterior"] is None
    assert marco["escenas"] == [
        {"id": primera, "lugar": "lug_00000001", "instante": "1584-10-15",
         "duracion": "una tarde"},
        {"id": segunda, "lugar": "lug_00000001", "instante": "1584-10-16",
         "duracion": "una tarde"},
    ]


def test_del_plan_solo_entra_el_marco(almacen: Almacen) -> None:
    """D-94: ni el objetivo, ni el elenco, ni el punto de vista."""
    id_obra = almacen.crear_obra({"titulo": "T", "epoca": "Salamanca, 1584"})
    almacen.guardar([_escena(id_obra, 1, 1, "1584-10-15")])
    encargo = guion.expandir(guion.paso(9), id_obra=id_obra, capitulo=1, escenas=())[0]
    texto = ensamblar(almacen, encargo).texto
    assert "cobrar la deuda" not in texto
    assert "elenco_presente" not in texto and "pov" not in texto


def test_la_fecha_de_cierre_anterior_es_la_mas_tardia_de_los_capitulos_previos(
    almacen: Almacen,
) -> None:
    id_obra = almacen.crear_obra({"titulo": "T", "epoca": "Salamanca, 1584"})
    for capitulo, fecha in ((1, "1584-10-15"), (1, "1584-10-20"), (2, "1584-11-02"),
                            (3, "1584-12")):
        almacen.anadir_eventos_de_estado(
            [Artefacto("EventoEstado",
                       {"tipo_de_evento": "transcurre_tiempo", "fecha_resultante": fecha},
                       id_obra=id_obra, capitulo=capitulo)]
        )

    assert _ventana_de_plegar(almacen, id_obra, 2)["fecha_de_cierre_anterior"] == "1584-10-20"
    assert _ventana_de_plegar(almacen, id_obra, 3)["fecha_de_cierre_anterior"] == "1584-11-02"


def test_el_planificador_recibe_la_epoca_y_la_fecha_de_cierre(almacen: Almacen) -> None:
    """RF-214: al planificar el capitulo N sus escenas aun no existen."""
    id_obra = almacen.crear_obra({"titulo": "T", "epoca": "Salamanca, 1584"})
    almacen.anadir_eventos_de_estado(
        [Artefacto("EventoEstado",
                   {"tipo_de_evento": "transcurre_tiempo", "fecha_resultante": "1584-05-18"},
                   id_obra=id_obra, capitulo=3)]
    )
    encargo = guion.expandir(guion.paso(1), id_obra=id_obra, capitulo=4, escenas=())[0]
    assert encargo.tarea == "planificar"
    marco = ensamblar(almacen, encargo).materiales["marco_temporal_del_capitulo"]
    assert marco == {"epoca": "Salamanca, 1584", "fecha_de_cierre_anterior": "1584-05-18",
                     "escenas": []}
    prompt = prompt_de_tarea("planificar")
    assert "no es anterior a la `fecha_de_cierre_anterior`" in prompt


def test_el_contable_recibe_el_reparto_y_los_lugares_con_su_id(almacen: Almacen) -> None:
    """RF-218: el Contable se inventaba un `id` por capitulo para la misma persona."""
    id_obra = almacen.crear_obra({"titulo": "T", "epoca": "Salamanca, 1584"})
    [ines] = almacen.guardar([Artefacto("Personaje", {"nombre": "Ines", "licencia": "plausible",
                                                     "voz": {"muletillas": ["a fe mia"]}},
                                        id_obra=id_obra)])
    [taller] = almacen.guardar([Artefacto("Lugar", {"nombre": "El taller",
                                                   "descripcion": "largo"}, id_obra=id_obra)])
    encargo = guion.expandir(guion.paso(9), id_obra=id_obra, capitulo=1, escenas=())[0]

    reparto = ensamblar(almacen, encargo).materiales["reparto_y_lugares"]

    assert reparto == {"personajes": [{"id": ines, "nombre": "Ines"}],
                       "lugares": [{"id": taller, "nombre": "El taller"}]}
    prompt = prompt_de_tarea("plegar")
    assert "no los inventas" in prompt
    assert "escribes su `viaja_a`" in prompt


def test_el_prompt_del_contable_dice_de_donde_sale_el_ano() -> None:
    prompt = prompt_de_tarea("plegar")
    assert "marco temporal" in prompt
    assert "fecha_de_cierre_anterior" in prompt
    assert "manda el texto" in prompt
