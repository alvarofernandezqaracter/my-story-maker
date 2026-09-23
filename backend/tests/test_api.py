"""Etapa 7: la API.

Cierre por `prueba`, `analisis` y `demostracion`: un brief al que le falta un
campo obligatorio se rechaza nombrando el campo y sin crear nada; se enumeran
las operaciones de escritura que ofrece la API y son exactamente cinco; y
detener y reanudar a mitad de capitulo no duplica ni pierde trabajo aceptado.
Evidencia: el esquema HTTP publicado y la lista de sus operaciones de escritura.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dobles import EjecutorFingido
from novela.api.aplicacion import crear_aplicacion, operaciones_de_escritura

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "capitulos_objetivo": 1,
    "politicas_globales": {"pov": "tercera_limitada"},
    "arcos": ["Ines pasa del miedo al desafio"],
}


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[TestClient]:
    app = crear_aplicacion(tmp_path / "api.sqlite3", ejecutor=EjecutorFingido())
    with TestClient(app) as cliente:
        yield cliente


def _obra_terminada(cliente: TestClient) -> str:
    respuesta = cliente.post("/obras", json=BRIEF)
    assert respuesta.status_code == 202
    id_obra = respuesta.json()["id_obra"]
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=60)
    assert not hilo.is_alive(), "la produccion no termino"
    return str(id_obra)


# --- Un brief incompleto ----------------------------------------------------


@pytest.mark.parametrize(
    "campo", ["titulo", "epoca", "premisa", "tesis_tematica", "capitulos_objetivo"]
)
def test_un_brief_sin_un_campo_obligatorio_se_rechaza_nombrando_el_campo(
    cliente: TestClient, campo: str
) -> None:
    incompleto = {clave: valor for clave, valor in BRIEF.items() if clave != campo}

    respuesta = cliente.post("/obras", json=incompleto)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert campo in cuerpo["campos"]
    assert campo in cuerpo["detalle"]
    assert cuerpo["detalle"].startswith("Falta un campo obligatorio")


def test_un_brief_rechazado_no_crea_nada(cliente: TestClient) -> None:
    cliente.post("/obras", json={"titulo": "solo el titulo"})
    produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
    assert produccion.almacen.listar_obras() == []


def test_los_mensajes_de_error_van_en_espanol(cliente: TestClient) -> None:
    respuesta = cliente.get("/obras/obr_inventada")
    assert respuesta.status_code == 404
    assert "No hay ninguna obra" in respuesta.json()["detail"]


# --- Las operaciones de escritura son cinco --------------------------------


def test_la_api_ofrece_exactamente_cinco_operaciones_de_escritura(
    cliente: TestClient,
) -> None:
    """Las dos de la entrevista, alta, detener y reanudar. La entrevista ocurre
    antes de que la obra exista, y detener y reanudar son control, no
    mantenimiento: no hay limpieza ni archivado que el editor deba ejecutar."""
    escrituras = operaciones_de_escritura(cliente.app)  # type: ignore[arg-type]

    assert escrituras == [
        "POST /entrevistas",
        "POST /entrevistas/{id_entrevista}/pasadas",
        "POST /obras",
        "POST /obras/{id_obra}/detener",
        "POST /obras/{id_obra}/reanudar",
    ]


def test_el_esquema_publicado_trae_las_catorce_rutas(cliente: TestClient) -> None:
    esquema = cliente.get("/openapi.json").json()
    rutas = sorted(esquema["paths"])
    assert rutas == [
        "/entrevistas",
        "/entrevistas/{id_entrevista}/pasadas",
        "/obras",
        "/obras/{id_obra}",
        "/obras/{id_obra}/capitulos/{numero}",
        "/obras/{id_obra}/criticas",
        "/obras/{id_obra}/detener",
        "/obras/{id_obra}/estado",
        "/obras/{id_obra}/manuscrito",
        "/obras/{id_obra}/pasajes",
        "/obras/{id_obra}/progreso",
        "/obras/{id_obra}/progreso/ahora",
        "/obras/{id_obra}/reanudar",
        "/obras/{id_obra}/trazas",
    ]


# --- Una obra corre con una sola llamada de escritura ----------------------


def test_una_obra_corre_de_una_sola_orden_hasta_cerrarse(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)

    ficha = cliente.get(f"/obras/{id_obra}").json()
    assert ficha["capitulos_cerrados"] == 1
    assert ficha["detenida"] is False

    manuscrito = cliente.get(f"/obras/{id_obra}/manuscrito").json()
    assert len(manuscrito["unidades"]) == 3
    assert all(unidad["texto"] for unidad in manuscrito["unidades"])


def test_la_api_sirve_lo_que_el_editor_necesita_ver(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)

    capitulo = cliente.get(f"/obras/{id_obra}/capitulos/1").json()
    assert capitulo["estado"] is None or capitulo["estado"]
    assert len(capitulo["escenas"]) == 3
    assert capitulo["borrador_vigente_por_escena"]

    trazas = cliente.get(f"/obras/{id_obra}/trazas").json()
    assert trazas and all(t["cerrada_en"] for t in trazas)
    assert cliente.get(f"/obras/{id_obra}/trazas?rol=redactor").json()

    estado = cliente.get(f"/obras/{id_obra}/estado?capitulo=1").json()
    assert estado["estado"] is not None
    assert len(estado["eventos"]) == 1

    progreso = cliente.get(f"/obras/{id_obra}/progreso/ahora").json()
    assert progreso["tareas_abiertas"] == []
    assert progreso["tokens_de_entrada_concurrentes"] == 0
    assert progreso["techo"] == 100_000


def test_las_criticas_se_filtran(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)
    todas = cliente.get(f"/obras/{id_obra}/criticas").json()
    assert isinstance(todas, list)
    filtradas = cliente.get(f"/obras/{id_obra}/criticas?severidad=bloqueante").json()
    assert all(c["severidad"] == "bloqueante" for c in filtradas)


# --- Detener y reanudar ------------------------------------------------------


def test_detener_y_reanudar_no_duplica_ni_pierde_trabajo_aceptado(
    cliente: TestClient,
) -> None:
    id_obra = _obra_terminada(cliente)
    antes = cliente.get(f"/obras/{id_obra}/manuscrito").json()["unidades"]

    detenida = cliente.post(f"/obras/{id_obra}/detener", json={"motivo": "a media tarde"})
    assert detenida.status_code == 200
    assert detenida.json()["detenida"] is True
    assert cliente.get(f"/obras/{id_obra}").json()["detenida"] is True

    reanudada = cliente.post(f"/obras/{id_obra}/reanudar")
    assert reanudada.status_code == 200
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=60)

    despues = cliente.get(f"/obras/{id_obra}/manuscrito").json()["unidades"]
    assert [u["texto"] for u in despues] == [u["texto"] for u in antes]


def test_detener_para_la_produccion_en_el_paso_siguiente(cliente: TestClient) -> None:
    """La orden de detener la ve el caminante antes de abrir el paso siguiente."""
    respuesta = cliente.post("/obras", json=BRIEF | {"capitulos_objetivo": 3})
    id_obra = respuesta.json()["id_obra"]
    cliente.post(f"/obras/{id_obra}/detener", json={"motivo": "a mitad"})
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=60)

    ficha = cliente.get(f"/obras/{id_obra}").json()
    assert ficha["detenida"] is True
    assert ficha["capitulos_cerrados"] < 3
