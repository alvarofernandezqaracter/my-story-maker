"""SPEC1 4.12: las versiones de la obra.

Metodo: `prueba`. Una obra de tres capitulos corre entera con un ejecutor
fingido que firma lo que escribe con la version en curso; se rehace desde el
capitulo 2 y se compara lo que sirve la version 1 antes y despues (RF-114). Se
siembran ademas las escrituras prohibidas contra las marcas nuevas y la
migracion sobre una base anterior. Evidencia: las respuestas de la API por
version y los disparadores que rechazan cada escritura.
"""

import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dobles import EjecutorFingido
from novela.almacen import Almacen, Artefacto, VersionNoAdmitida, esquema
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.conexion import abrir, escritura
from novela.almacen.migraciones import MIGRACIONES, aplicar
from novela.api.aplicacion import crear_aplicacion
from novela.nucleo import versiones
from novela.nucleo.caminante import Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana
from novela.tareas import CatalogoDelRepositorio

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "arcos": ["Ines pasa del miedo al desafio"],
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 3,
}


PROSA_DE_ESCENA = "Version cosida de la escena. " + "tinta " * 400


@dataclass
class EjecutorFirmado:
    """El fingido de siempre, que firma la prosa y el lugar con `firma`.

    Cambiar la firma antes de rehacer es lo que deja distinguir el mundo de una
    version del de la otra sin depender de lo que conteste un modelo.
    """

    firma: str = "v1"
    # Cada escena cosida trae lo bastante para que el capitulo tenga la longitud
    # de un capitulo y la version pase la puerta de publicacion (RF-143).
    interno: EjecutorFingido = field(
        default_factory=lambda: EjecutorFingido(texto_cosido=PROSA_DE_ESCENA)
    )

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        resultado = self.interno.ejecutar(encargo, ventana)
        for artefacto in resultado.artefactos:
            if artefacto.tipo == "Borrador":
                artefacto.cuerpo = artefacto.cuerpo | {
                    "texto": f"[{self.firma}] {artefacto.cuerpo.get('texto', '')}"
                }
            if artefacto.tipo == "EventoEstado":
                artefacto.cuerpo = artefacto.cuerpo | {
                    "lugar_resultante": f"{artefacto.cuerpo['lugar_resultante']}-{self.firma}"
                }
        if resultado.estado_en_n is not None:
            resultado.estado_en_n = resultado.estado_en_n | {"firma": self.firma}
        return resultado


@pytest.fixture
def ejecutor() -> EjecutorFirmado:
    return EjecutorFirmado()


@pytest.fixture
def cliente(tmp_path: Path, ejecutor: EjecutorFirmado) -> Iterator[TestClient]:
    app = crear_aplicacion(tmp_path / "versiones.sqlite3", ejecutor=ejecutor)
    with TestClient(app) as cliente:
        yield cliente


def _esperar(cliente: TestClient, id_obra: str) -> None:
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=120)
    assert not hilo.is_alive(), "la produccion no termino"


def _obra_terminada(cliente: TestClient) -> str:
    respuesta = cliente.post("/obras", json=BRIEF)
    assert respuesta.status_code == 202
    id_obra = str(respuesta.json()["id_obra"])
    _esperar(cliente, id_obra)
    return id_obra


def _lo_que_sirve(cliente: TestClient, id_obra: str, version: int) -> dict[str, Any]:
    """Todo lo que la API sirve de una version, para compararlo entero."""
    q = f"version={version}"
    manuscrito = cliente.get(f"/obras/{id_obra}/manuscrito?{q}").json()
    manuscrito.pop("publicada")
    return {
        "manuscrito": manuscrito,
        "capitulos": [
            cliente.get(f"/obras/{id_obra}/capitulos/{n}?{q}").json() for n in (1, 2, 3)
        ],
        "criticas": cliente.get(f"/obras/{id_obra}/criticas?{q}").json(),
        "estado": [
            cliente.get(f"/obras/{id_obra}/estado?capitulo={n}&{q}").json() for n in (1, 2, 3)
        ],
        "hechos": cliente.get(f"/obras/{id_obra}/hechos?{q}").json(),
        "cronologia": cliente.get(f"/obras/{id_obra}/cronologia?{q}").json(),
    }


# --- Criterio 8: rehacer desde el 2 y la version 1 sigue como estaba -------


def test_rehacer_desde_un_capitulo_conserva_la_version_anterior_entera(
    cliente: TestClient, ejecutor: EjecutorFirmado
) -> None:
    id_obra = _obra_terminada(cliente)
    antes = _lo_que_sirve(cliente, id_obra, 1)
    assert antes["estado"][2]["estado"]["firma"] == "v1"

    ejecutor.firma = "v2"
    respuesta = cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 2})
    assert respuesta.status_code == 202
    assert respuesta.json()["version"] == 2
    assert respuesta.json()["capitulos_cambiados"] == [2, 3]
    _esperar(cliente, id_obra)

    # RF-114: lo que se sirve de la version 1 no ha cambiado en nada.
    assert _lo_que_sirve(cliente, id_obra, 1) == antes

    # La 2 comparte el capitulo 1 y reescribe el 2 y el 3, con su propio mundo.
    v1 = antes["manuscrito"]["unidades"]
    v2 = cliente.get(f"/obras/{id_obra}/manuscrito?version=2").json()["unidades"]
    assert [u["escena"] for u in v2 if u["capitulo"] == 1] == [
        u["escena"] for u in v1 if u["capitulo"] == 1
    ]
    assert all(u["texto"].startswith("[v1]") for u in v2 if u["capitulo"] == 1)
    assert all(u["texto"].startswith("[v2]") for u in v2 if u["capitulo"] > 1)
    assert not {u["escena"] for u in v2 if u["capitulo"] > 1} & {u["escena"] for u in v1}
    estado_v2 = cliente.get(f"/obras/{id_obra}/estado?capitulo=3&version=2").json()
    assert estado_v2["estado"]["firma"] == "v2"
    assert [e["lugar_resultante"] for e in estado_v2["eventos"]] == [
        "lug_0001-v1",
        "lug_0002-v2",
        "lug_0003-v2",
    ]
    cronologia_v2 = cliente.get(f"/obras/{id_obra}/cronologia?version=2").json()["sucesos"]
    assert [s["lugar"] for s in cronologia_v2 if s["origen"] == "evento_de_estado"] == [
        "lug_0001-v1",
        "lug_0002-v2",
        "lug_0003-v2",
    ]

    lista = cliente.get(f"/obras/{id_obra}/versiones").json()
    assert [(v["numero"], v["base"], v["capitulos_cambiados"]) for v in lista] == [
        (1, None, []),
        (2, 1, [2, 3]),
    ]
    assert all(v["terminada"] and not v["publicada"] for v in lista)


def test_publicar_es_una_orden_y_manda_sobre_lo_que_se_lee(
    cliente: TestClient, ejecutor: EjecutorFirmado
) -> None:
    id_obra = _obra_terminada(cliente)
    # Terminar no publica: sin publicada, se lee la ultima y se dice.
    manuscrito = cliente.get(f"/obras/{id_obra}/manuscrito").json()
    assert (manuscrito["version"], manuscrito["publicada"]) == (1, False)
    assert cliente.get(f"/obras/{id_obra}").json()["version_publicada"] is None

    publicada = cliente.post(f"/obras/{id_obra}/versiones/1/publicar")
    assert publicada.status_code == 200
    ejecutor.firma = "v2"
    cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 3})
    _esperar(cliente, id_obra)

    # Con la 1 publicada, la 2 terminada no se sirve hasta que se publique.
    manuscrito = cliente.get(f"/obras/{id_obra}/manuscrito").json()
    assert (manuscrito["version"], manuscrito["publicada"]) == (1, True)
    ficha = cliente.get(f"/obras/{id_obra}").json()
    assert (ficha["version_en_curso"], ficha["version_publicada"]) == (2, 1)

    assert cliente.post(f"/obras/{id_obra}/versiones/2/publicar").status_code == 200
    manuscrito = cliente.get(f"/obras/{id_obra}/manuscrito").json()
    assert (manuscrito["version"], manuscrito["publicada"]) == (2, True)
    assert any(u["texto"].startswith("[v2]") for u in manuscrito["unidades"])

    # Volver a publicar la anterior tambien queda escrito, y manda la ultima.
    assert cliente.post(f"/obras/{id_obra}/versiones/1/publicar").status_code == 200
    assert cliente.get(f"/obras/{id_obra}/manuscrito").json()["version"] == 1
    produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
    filas = produccion.almacen._lector.execute(
        "SELECT numero FROM publicacion_de_version WHERE id_obra = ? ORDER BY id", (id_obra,)
    ).fetchall()
    assert [f["numero"] for f in filas] == [1, 2, 1]


def test_lo_que_no_se_admite_se_rechaza_sin_crear_nada(cliente: TestClient) -> None:
    respuesta = cliente.post("/obras", json=BRIEF)
    id_obra = respuesta.json()["id_obra"]
    produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
    produccion.almacen.detener(id_obra, "para probar")
    _esperar(cliente, id_obra)

    # Sin terminar no se publica ni se rehace.
    assert cliente.post(f"/obras/{id_obra}/versiones/1/publicar").status_code == 409
    rehacer = cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 1})
    assert rehacer.status_code == 409
    # Ni desde un capitulo que no existe, ni sobre una version que no existe.
    fuera = cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 4})
    assert fuera.status_code == 422
    assert cliente.post(f"/obras/{id_obra}/versiones/9/publicar").status_code == 404
    assert cliente.get(f"/obras/{id_obra}/manuscrito?version=9").status_code == 404
    assert len(produccion.almacen.listar_versiones(id_obra)) == 1
    assert produccion.almacen.version_publicada(id_obra) is None


def test_tres_versiones_en_fila_cada_una_ve_lo_suyo_y_el_indice_solo_lo_vivo(
    cliente: TestClient, ejecutor: EjecutorFirmado
) -> None:
    """La 3 sale de la 2, que salio de la 1: cada una sigue sirviendo lo que
    servia, y la 3 comparte el capitulo 1 con la 1 y el 2 con la 2 (RF-113)."""
    id_obra = _obra_terminada(cliente)
    antes_v1 = _lo_que_sirve(cliente, id_obra, 1)
    ejecutor.firma = "v2"
    cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 2})
    _esperar(cliente, id_obra)
    antes_v2 = _lo_que_sirve(cliente, id_obra, 2)
    ejecutor.firma = "v3"
    respuesta = cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 3})
    assert respuesta.json()["version"] == 3
    _esperar(cliente, id_obra)

    assert _lo_que_sirve(cliente, id_obra, 1) == antes_v1
    assert _lo_que_sirve(cliente, id_obra, 2) == antes_v2
    v3 = cliente.get(f"/obras/{id_obra}/manuscrito?version=3").json()["unidades"]
    firmas: dict[int, set[str]] = {}
    for unidad in v3:
        firmas.setdefault(unidad["capitulo"], set()).add(unidad["texto"].split(" ")[0])
    assert firmas == {1: {"[v1]"}, 2: {"[v2]"}, 3: {"[v3]"}}

    # RF-111: ningun fragmento del indice apunta a algo relevado.
    produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
    fragmentos = produccion.almacen._lector.execute(
        "SELECT artefacto, tipo_de_artefacto FROM fragmento WHERE id_obra = ?", (id_obra,)
    ).fetchall()
    assert fragmentos
    for fragmento in fragmentos:
        artefacto = produccion.almacen.leer(
            fragmento["tipo_de_artefacto"], fragmento["artefacto"], incluir_caducados=True
        )
        assert artefacto is not None and artefacto.relevado_por is None, fragmento["artefacto"]


def test_no_se_rehace_mientras_la_obra_produce(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)
    produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
    suelta = threading.Event()
    hilo = threading.Thread(target=suelta.wait, daemon=True)
    hilo.start()
    produccion.hilos[id_obra] = hilo
    try:
        respuesta = cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 1})
    finally:
        suelta.set()
        hilo.join()
    assert respuesta.status_code == 409
    assert "produciendo" in respuesta.json()["detail"]
    assert len(produccion.almacen.listar_versiones(id_obra)) == 1


# --- El mundo de cada version, en el almacen --------------------------------


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "mundo.sqlite3")
    yield almacen
    almacen.cerrar()


def _evento_del_capitulo(almacen: Almacen, id_obra: str, capitulo: int) -> str:
    """Un `Evento` del mundo, que no lleva capitulo, escrito por una tarea del
    capitulo dado, como los que anade el Planificador."""
    traza = almacen.abrir_traza(
        id_obra,
        rol="planificador",
        tarea="planificar",
        intento=1,
        capitulo=capitulo,
        escena=None,
        contexto="",
        tokens_estimados=0,
    )
    return almacen.guardar(
        [
            Artefacto(
                "Evento",
                {"descripcion": f"motin {capitulo}"},
                id_obra=id_obra,
                procedencia_rol="planificador",
                procedencia_tarea=traza,
            )
        ]
    )[0]


def _terminar(almacen: Almacen, id_obra: str, hasta: int) -> None:
    almacen.guardar_auditoria(id_obra, hasta, [], lambda _l, _r: None, de_cierre=True)  # type: ignore[arg-type,return-value]


def test_lo_que_cuelga_de_un_capitulo_rehecho_se_releva_y_lo_de_antes_se_comparte(
    almacen: Almacen,
) -> None:
    id_obra = almacen.crear_obra({"titulo": "Obra", "capitulos_objetivo": 2})
    personaje = almacen.guardar([Artefacto("Personaje", {"nombre": "Ines"}, id_obra=id_obra)])[
        0
    ]
    del_uno = _evento_del_capitulo(almacen, id_obra, 1)
    del_dos = _evento_del_capitulo(almacen, id_obra, 2)
    for numero in (1, 2):
        almacen.anadir_eventos_de_estado(
            [Artefacto("EventoEstado", {"n": numero}, id_obra=id_obra, capitulo=numero)]
        )
        almacen.materializar_estado(id_obra, numero, {"en": numero})
    _terminar(almacen, id_obra, 2)

    assert versiones.rehacer_desde(almacen, None, id_obra, 2, 2) == 2

    vivos = {e.id for e in almacen.listar("Evento", id_obra)}
    assert vivos == {del_uno}, "el Evento del capitulo rehecho sale de lo vivo"
    assert {e.id for e in almacen.listar("Evento", id_obra, version=1)} == {del_uno, del_dos}
    assert [p.id for p in almacen.listar("Personaje", id_obra, version=2)] == [personaje]
    relevado = almacen.leer("Evento", del_dos, incluir_caducados=True)
    assert relevado is not None and relevado.relevado_por == 2
    assert [e.cuerpo["n"] for e in almacen.listar("EventoEstado", id_obra)] == [1]
    # El estado en N se releva con su version, no se borra (RF-115).
    assert almacen.estado_en(id_obra, 2) is None
    assert almacen.estado_en(id_obra, 2, version=1) == {"en": 2}
    assert almacen.estado_en(id_obra, 1, version=2) == {"en": 1}
    # Lo que se escribe ahora es de la version 2 y la 1 no lo ve.
    almacen.materializar_estado(id_obra, 2, {"en": "otro"})
    nuevo = almacen.anadir_eventos_de_estado(
        [Artefacto("EventoEstado", {"n": 22}, id_obra=id_obra, capitulo=2)]
    )[0]
    assert almacen.leer("EventoEstado", nuevo).version_de_obra == 2  # type: ignore[union-attr]
    assert [e.cuerpo["n"] for e in almacen.listar("EventoEstado", id_obra, version=1)] == [1, 2]
    assert almacen.estado_en(id_obra, 2, version=1) == {"en": 2}
    assert almacen.estado_en(id_obra, 2) == {"en": "otro"}
    # Y la produccion de la 2 no ha terminado: la 1 si.
    assert almacen.auditada_hasta(id_obra) == 1
    assert [v["terminada_en"] is not None for v in almacen.listar_versiones(id_obra)] == [
        True,
        False,
    ]


def test_descartar_un_capitulo_a_medias_se_lleva_lo_que_escribio_sin_capitulo(
    almacen: Almacen,
) -> None:
    """RF-118: un `Evento` anadido en un capitulo que no llego a cerrar no se
    queda en el mundo."""
    id_obra = almacen.crear_obra({"titulo": "Obra"})
    del_uno = _evento_del_capitulo(almacen, id_obra, 1)
    del_dos = _evento_del_capitulo(almacen, id_obra, 2)

    almacen.descartar_desde(id_obra, 2)

    assert {e.id for e in almacen.listar("Evento", id_obra)} == {del_uno}
    descartado = almacen.leer("Evento", del_dos, incluir_caducados=True)
    assert descartado is not None and descartado.caducado_en and descartado.relevado_por is None
    # Un caducado sin relevo no lo ve ninguna version.
    assert {e.id for e in almacen.listar("Evento", id_obra, version=1)} == {del_uno}


def test_las_marcas_de_version_no_se_tocan(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra({"titulo": "Obra"})
    id_evento = almacen.anadir_eventos_de_estado(
        [Artefacto("EventoEstado", {}, id_obra=id_obra, capitulo=1)]
    )[0]
    conexion = almacen._escritor
    with pytest.raises(sqlite3.IntegrityError, match="version en que nacio"):
        conexion.execute(
            "UPDATE artefacto_evento_estado SET version_de_obra = 5 WHERE id = ?", (id_evento,)
        )
    with pytest.raises(sqlite3.IntegrityError, match="junto al caducado"):
        conexion.execute(
            "UPDATE artefacto_evento_estado SET relevado_por = 2 WHERE id = ?", (id_evento,)
        )
    conexion.execute(
        "UPDATE artefacto_evento_estado SET caducado_en = 'x', relevado_por = 2 WHERE id = ?",
        (id_evento,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="una vez"):
        conexion.execute(
            "UPDATE artefacto_evento_estado SET relevado_por = 3 WHERE id = ?", (id_evento,)
        )
    with pytest.raises(sqlite3.IntegrityError, match="no se borra"):
        conexion.execute("DELETE FROM version_de_la_obra WHERE id_obra = ?", (id_obra,))
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        conexion.execute(
            "UPDATE version_de_la_obra SET capitulos_cambiados = '[9]' WHERE id_obra = ?",
            (id_obra,),
        )
    _terminar(almacen, id_obra, 1)
    with pytest.raises(sqlite3.IntegrityError, match="una sola vez"):
        conexion.execute(
            "UPDATE version_de_la_obra SET terminada_en = 'y' WHERE id_obra = ?", (id_obra,)
        )
    # Aqui se prueban los disparadores del registro, no la puerta: se escribe la
    # publicacion directamente.
    almacen.publicar_version(id_obra, 1)
    with pytest.raises(sqlite3.IntegrityError, match="no se borra"):
        conexion.execute("DELETE FROM publicacion_de_version WHERE id_obra = ?", (id_obra,))
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        conexion.execute(
            "UPDATE publicacion_de_version SET numero = 1 WHERE id_obra = ?", (id_obra,)
        )


def test_sin_terminar_no_se_publica_ni_se_rehace(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra({"titulo": "Obra"})
    with pytest.raises(VersionNoAdmitida):
        versiones.publicar(almacen, id_obra, 1, CatalogoDelRepositorio())
    with pytest.raises(VersionNoAdmitida):
        versiones.rehacer_desde(almacen, None, id_obra, 1, 1)
    assert versiones.de_referencia(almacen, id_obra) == 1


# --- La migracion sobre una base anterior -----------------------------------


def test_las_obras_que_ya_existian_son_su_version_1(tmp_path: Path) -> None:
    conexion = abrir(tmp_path / "vieja.sqlite3")
    anteriores = [m for m in MIGRACIONES if m[0] < esquema.MIGRACION_DE_LAS_VERSIONES]
    for numero, nombre, sentencias in anteriores:
        with escritura(conexion):
            for sentencia in sentencias():
                conexion.execute(sentencia)
            conexion.execute(
                "INSERT INTO migracion (numero, nombre, aplicada_en) VALUES (?, ?, 'x')",
                (numero, nombre),
            )
    with escritura(conexion):
        for id_obra, auditada in (("obr_1", 1), ("obr_2", 0)):
            conexion.execute(
                "INSERT INTO artefacto_obra (id, id_obra, tipo, cuerpo, memoria, creado_en) "
                "VALUES (?, ?, 'Obra', '{\"capitulos_objetivo\": 1}', 'obra', 'x')",
                (id_obra, id_obra),
            )
            conexion.execute(
                "INSERT INTO control_de_ejecucion (id_obra, detenida, actualizado_en, "
                "auditada_hasta) VALUES (?, 0, 'x', ?)",
                (id_obra, auditada),
            )
        conexion.execute(
            "INSERT INTO cache_estado_materializado (id_obra, capitulo, cuerpo, calculado_en) "
            "VALUES ('obr_1', 1, '{\"en\": 1}', 'x')"
        )

    assert aplicar(conexion) == MIGRACIONES[-1][0]

    filas = conexion.execute(
        "SELECT id_obra, numero, base, terminada_en FROM version_de_la_obra ORDER BY id_obra"
    ).fetchall()
    assert [(f["id_obra"], f["numero"], f["base"]) for f in filas] == [
        ("obr_1", 1, None),
        ("obr_2", 1, None),
    ]
    assert filas[0]["terminada_en"] is not None and filas[1]["terminada_en"] is None
    cache = conexion.execute(
        "SELECT version_de_obra, relevado_por, cuerpo FROM cache_estado_materializado"
    ).fetchone()
    assert (cache["version_de_obra"], cache["relevado_por"], cache["cuerpo"]) == (
        1,
        None,
        '{"en": 1}',
    )
    obra = conexion.execute("SELECT version_de_obra FROM artefacto_obra").fetchone()
    assert obra["version_de_obra"] == 1
    conexion.close()
