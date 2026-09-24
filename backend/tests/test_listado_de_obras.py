"""SPEC1 4.22: el listado de obras y su situacion.

Cierre por `prueba`, sin gastar y sin caminar ninguna obra: las obras se dan de
alta en el almacen de la aplicacion ya arrancada, que no relanza nada despues
de arrancar, y cada situacion se provoca con la misma operacion del almacen que
la provoca en produccion. Evidencia: lo que sirven `GET /obras` y `GET /obras/{id}`.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dobles import EjecutorFingido
from novela.almacen import Almacen
from novela.api.aplicacion import crear_aplicacion
from novela.nucleo import versiones
from novela.vocabularios import SITUACION_DE_LA_OBRA


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[TestClient]:
    app = crear_aplicacion(tmp_path / "listado.sqlite3", ejecutor=EjecutorFingido())
    with TestClient(app) as cliente:
        yield cliente


def _almacen(cliente: TestClient) -> Almacen:
    return cliente.app.state.produccion.almacen  # type: ignore[attr-defined,no-any-return]


def _alta(cliente: TestClient, titulo: str, **cuerpo: Any) -> str:
    return _almacen(cliente).crear_obra(
        {"titulo": titulo, "epoca": "Sevilla, 1587", "capitulos_objetivo": 3, **cuerpo}
    )


def _terminar(almacen: Almacen, id_obra: str) -> None:
    """La auditoria de cierre, que es lo que termina la version en curso (RF-110)."""
    almacen.guardar_auditoria(id_obra, 3, [], lambda _l, _r: None, de_cierre=True)  # type: ignore[arg-type,return-value]


def _situaciones(cliente: TestClient) -> dict[str, str]:
    return {o["id_obra"]: o["situacion"] for o in cliente.get("/obras").json()}


def test_sin_obras_la_lista_esta_vacia_y_no_es_un_error(cliente: TestClient) -> None:
    respuesta = cliente.get("/obras")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_salen_todas_de_la_mas_reciente_a_la_mas_antigua(cliente: TestClient) -> None:
    primera = _alta(cliente, "La primera")
    segunda = _alta(cliente, "La segunda")
    tercera = _alta(cliente, "La tercera")

    obras = cliente.get("/obras").json()

    assert [o["id_obra"] for o in obras] == [tercera, segunda, primera]


def test_cada_obra_lleva_la_misma_ficha_que_su_ruta(cliente: TestClient) -> None:
    id_obra = _alta(
        cliente,
        "El taller",
        destinatario={"nombre": "Lucia", "dedicatoria": "Para Lucia"},
    )

    (listada,) = cliente.get("/obras").json()
    ficha = cliente.get(f"/obras/{id_obra}").json()

    assert {clave: listada[clave] for clave in ficha} == ficha
    assert listada["epoca"] == "Sevilla, 1587"
    assert listada["capitulos_objetivo"] == 3
    assert listada["creada_en"]
    assert ficha["destinatario"] == "Lucia"


def test_la_situacion_sigue_a_la_obra_por_sus_cuatro_valores(cliente: TestClient) -> None:
    almacen = _almacen(cliente)
    id_obra = _alta(cliente, "La que recorre todo")

    assert _situaciones(cliente)[id_obra] == "en_produccion"

    almacen.detener(id_obra, "lo detuvo el editor")
    assert _situaciones(cliente)[id_obra] == "detenida"

    almacen.reanudar(id_obra)
    _terminar(almacen, id_obra)
    assert _situaciones(cliente)[id_obra] == "terminada"

    almacen.publicar_version(id_obra, 1)
    assert _situaciones(cliente)[id_obra] == "publicada"

    # Rehacer abre una version nueva sin terminar: vuelve a producirse.
    almacen.abrir_version(id_obra, 2, 3)
    assert _situaciones(cliente)[id_obra] == "en_produccion"


def test_detenida_manda_sobre_todo_lo_demas(cliente: TestClient) -> None:
    almacen = _almacen(cliente)
    id_obra = _alta(cliente, "Terminada y detenida")
    _terminar(almacen, id_obra)
    almacen.publicar_version(id_obra, 1)
    almacen.detener(id_obra, "motivo")

    assert versiones.situacion(almacen, id_obra) == "detenida"
    assert _situaciones(cliente)[id_obra] == "detenida"


def test_la_ficha_dice_la_misma_situacion_que_el_listado(cliente: TestClient) -> None:
    almacen = _almacen(cliente)
    en_produccion = _alta(cliente, "Una")
    terminada = _alta(cliente, "Dos")
    _terminar(almacen, terminada)

    for id_obra, situacion in _situaciones(cliente).items():
        assert cliente.get(f"/obras/{id_obra}").json()["situacion"] == situacion
    assert _situaciones(cliente) == {en_produccion: "en_produccion", terminada: "terminada"}


def test_el_contrato_cierra_la_situacion_al_vocabulario() -> None:
    esquema = crear_aplicacion().openapi()["components"]["schemas"]
    cerrada = esquema["FichaDeObra"]["properties"]["situacion"]["enum"]

    assert tuple(cerrada) == SITUACION_DE_LA_OBRA
    assert "ObraDelTaller" in esquema
