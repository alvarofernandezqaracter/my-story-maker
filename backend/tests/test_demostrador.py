"""SPEC1 4.16: el validador formal de la cronologia, con Lean 4.

Metodo: `prueba`, sin gastar. El volcado y la lectura de la salida de Lean se
prueban sin Lean. Lo que ejecuta `lake build` de verdad se salta limpio si Lean
no esta en la maquina, para no romper la bateria en otra; en la de desarrollo
corre y pasa. Evidencia: el estado de la comprobacion, los teoremas que Lean no
demostro, los codigos y cuerpos de la API y las criticas guardadas.

El caso fabricado (RF-156): una obra entera con el ejecutor fingido, limpia para
los cuatro validadores programaticos —esquema, nombres, longitud y elementos
personalizados—, en la que el Contable deja a Ines de Salcedo en dos lugares el
mismo dia del capitulo 2. Solo Lean lo ve, la version no se publica y el fallo
vuelve como critica del capitulo 2.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from novela import demostrador
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.api.aplicacion import crear_aplicacion
from novela.demostrador import DemostradorLean, intervalo, leer_salida, volcar
from novela.nucleo import versiones
from novela.vocabularios import INVARIANTE_DE_LA_CRONOLOGIA
from test_validadores import EjecutorDeLaPuerta, _obra_terminada, _publicaciones

HAY_LEAN = demostrador.buscar_lake() is not None
con_lean = pytest.mark.skipif(not HAY_LEAN, reason="Lean (lake) no esta instalado aqui")

INES = {"id": "per_1", "nombre": "Ines", "nacimiento": "1551"}
PEDRO = {"id": "per_2", "nombre": "Pedro", "nacimiento": "1560-03"}


def _suceso(id_: str, capitulo: int | None, momento: str | None, lugar: str | None,
            presentes: list[dict[str, Any]], muere: str | None = None,
            llega: str | None = None) -> dict[str, Any]:
    return {"id": id_, "capitulo": capitulo, "momento": momento, "lugar": lugar,
            "presentes": presentes, "muere": muere, "llega": llega}


COHERENTE = [
    _suceso("evs_1", 1, "1587-04-01", "lug_1", [INES, PEDRO]),
    _suceso("evs_2", 2, "1587-04-02", "lug_2", [INES, PEDRO], muere="per_2"),
    _suceso("eve_1", None, "1571", None, [INES]),
    _suceso("evs_3", 3, "1587-05", "lug_1", [INES]),
    _suceso("eve_2", None, None, None, []),
]

# Una cronologia rota por cada invariante, y el suceso que Lean tiene que senalar.
ROTAS = {
    "orden_temporal": (
        [_suceso("evs_1", 1, "1587-04-01", "lug_1", [INES]),
         _suceso("evs_2", 2, "1586", "lug_1", [INES])],
        "evs_1",
    ),
    "edad_coherente": (
        [_suceso("evs_1", 1, "1549-06-01", "lug_1", [INES])],
        "evs_1",
    ),
    "un_solo_lugar": (
        [_suceso("evs_1", 1, "1587-04-01", "lug_1", [INES]),
         _suceso("evs_2", 1, "1587-04-01", "lug_2", [INES])],
        "evs_1",
    ),
    "no_reaparece": (
        [_suceso("evs_1", 1, "1587-04-01", "lug_1", [INES, PEDRO], muere="per_2"),
         _suceso("evs_2", 2, "1587-04-02", "lug_1", [INES, PEDRO])],
        "evs_1",
    ),
}


# --- El volcado, sin Lean -----------------------------------------------------


def test_una_fecha_iso_parcial_es_un_intervalo_de_dias() -> None:
    assert intervalo("1587") == (15870101, 15871231)
    assert intervalo("1587-04") == (15870401, 15870431)
    assert intervalo("1587-04-03") == (15870403, 15870403)
    assert intervalo(None) == (demostrador.SIN_DESDE, demostrador.SIN_HASTA)
    for mala in ("abril de 1587", "87", "1587-13", "1587-04-32", "1587/04/03"):
        assert intervalo(mala) is None, mala


def test_el_volcado_escribe_un_teorema_por_invariante_y_suceso() -> None:
    volcado = volcar(COHERENTE)
    assert "import Cronologia.Invariantes" in volcado.texto
    assert "theorem cronologia_coherente : Coherente cronologia" in volcado.texto
    lineas = volcado.texto.splitlines()
    por_invariante: dict[str, list[str]] = {}
    for numero, teorema in volcado.teoremas.items():
        # La linea anotada es la del teorema: es lo que dice Lean al fallar.
        assert lineas[numero - 1].startswith(f"theorem {teorema.nombre} :")
        por_invariante.setdefault(teorema.invariante, []).append(teorema.suceso["id"])
    assert set(por_invariante) == set(INVARIANTE_DE_LA_CRONOLOGIA)
    for sucesos in por_invariante.values():
        assert sucesos == [s["id"] for s in COHERENTE]
    assert volcado.no_volcable == []


def test_lo_que_no_es_fecha_iso_parcial_no_se_vuelca_y_se_dice() -> None:
    rota = [_suceso("evs_1", 1, "primavera de 1587", "lug_1",
                    [{"id": "per_1", "nacimiento": "hacia 1550"}])]
    volcado = volcar(rota)
    campos = [(s["id"], campo, escrito) for s, campo, escrito in volcado.no_volcable]
    assert campos == [
        ("evs_1", "momento", "primavera de 1587"),
        ("evs_1", "nacimiento de per_1", "hacia 1550"),
    ]


def test_la_salida_de_lean_se_lee_por_teorema() -> None:
    volcado = volcar(ROTAS["no_reaparece"][0])
    linea = next(n for n, t in volcado.teoremas.items() if t.nombre == "reaparece_s1")
    salida = (
        f"error: Cronologia/Obra.lean:{linea}:60: Tactic `decide` proved that the "
        "proposition\n  ∀ (b : Suceso), b ∈ cronologia → NoReaparece s1 b\nis false\n"
        "error: build failed\n"
    )
    fallos = leer_salida(volcado, salida)
    assert [(f["invariante"], f["suceso"], f["capitulo"]) for f in fallos] == [
        ("no_reaparece", "evs_1", 1)
    ]
    assert "reaparece_s1" in fallos[0]["evidencia"]
    # Un error que no es de ningun teorema no se pierde: vuelve sin suceso.
    rotos = leer_salida(volcado, "error: Cronologia/Obra.lean:3:1: unknown identifier\n")
    assert [(f["invariante"], f["suceso"]) for f in rotos] == [("sin_atribuir", None)]


def test_sin_lean_no_se_comprueba_y_se_dice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demostrador, "buscar_lake", lambda: None)
    resultado = DemostradorLean().comprobar(ROTAS["no_reaparece"][0])
    assert resultado == {"comprobacion": "sin_comprobacion", "fallos": []}


# --- Con Lean de verdad -------------------------------------------------------


@con_lean
def test_lean_demuestra_una_cronologia_coherente() -> None:
    lean = DemostradorLean()
    resultado = lean.comprobar(COHERENTE)
    assert resultado == {"comprobacion": "demostrada", "fallos": []}, lean.salida
    assert "Built Cronologia.Obra" in lean.salida
    assert "Build completed successfully" in lean.salida


@con_lean
@pytest.mark.parametrize("invariante", INVARIANTE_DE_LA_CRONOLOGIA)
def test_lean_no_demuestra_una_cronologia_rota(invariante: str) -> None:
    sucesos, senalado = ROTAS[invariante]
    lean = DemostradorLean()
    resultado = lean.comprobar(sucesos)
    assert resultado["comprobacion"] == "fallida", lean.salida
    assert "error: build failed" in lean.salida
    assert (invariante, senalado) in {
        (f["invariante"], f["suceso"]) for f in resultado["fallos"]
    }, resultado["fallos"]
    # Cada rota rompe solo su invariante: los otros tres siguen demostrados.
    assert {f["invariante"] for f in resultado["fallos"]} == {invariante}


@con_lean
def test_dos_lugares_el_mismo_dia_pasan_si_consta_el_viaje() -> None:
    """SPEC1 RF-213: del taller a la biblioteca el mismo dia, con su `viaja_a`,
    y lo que hace alli despues."""
    cronologia = [
        _suceso("evs_1", 1, "1584-05-10", "lug_1", [INES]),
        _suceso("evs_2", 1, "1584-05-10", "lug_2", [INES, PEDRO], llega="per_1"),
        _suceso("evs_3", 1, "1584-05-10", "lug_2", [INES, PEDRO]),
    ]
    resultado = DemostradorLean().comprobar(cronologia)
    assert resultado["comprobacion"] == "demostrada", resultado["fallos"]


@con_lean
def test_el_viaje_de_otro_no_explica_a_quien_no_viajo() -> None:
    """Pedro llega a lug_2; Ines, que estaba en lug_1 ese dia, no viajo."""
    cronologia = [
        _suceso("evs_1", 1, "1605-03-12", "lug_1", [INES]),
        _suceso("evs_2", 1, "1605-03-12", "lug_2", [INES, PEDRO], llega="per_2"),
    ]
    resultado = DemostradorLean().comprobar(cronologia)
    assert resultado["comprobacion"] == "fallida"
    fallados = {f["detalle"].split(":")[0] for f in resultado["fallos"]}
    assert fallados == {"un_solo_lugar"}
    assert "sin que conste que viajase" in resultado["fallos"][0]["detalle"]


def test_el_suceso_viaja_a_lleva_quien_llega_en_el_volcado() -> None:
    volcado = volcar([_suceso("evs_1", 1, "1584-05-10", "lug_1", [INES], llega="per_1")])
    assert "UnSoloLugar cronologia s1 b" in volcado.texto
    assert "[⟨1, 15510101, 15511231⟩], 0, 1⟩" in volcado.texto


def test_lo_que_no_es_un_id_se_vuelca_como_no_consta() -> None:
    """SPEC1 RF-215: un `Evento` del mundo con el lugar descrito, no referido."""
    raro = _suceso("eve_1", None, "1584", None, [{"id": {"nombre": "x"}, "nacimiento": None}])
    raro["lugar"] = {"id": "Espana-universidades", "region": "Castilla"}
    volcado = volcar([_suceso("evs_1", 1, "1584-05-10", "lug_1", [INES]), raro])
    esperado = "def s2 : Suceso := ⟨0, 15840101, 15841231, 0, [⟨0, 0, 99999999⟩], 0, 0⟩"
    assert esperado in volcado.texto
    assert "-- lugar 1: lug_1" in volcado.texto and "-- lugar 2" not in volcado.texto


@con_lean
def test_el_directorio_de_lean_no_queda_en_disco(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demostrador.tempfile, "tempdir", str(tmp_path))
    DemostradorLean().comprobar(COHERENTE)
    assert list(tmp_path.iterdir()) == []
    assert not (demostrador.PROYECTO / "Cronologia" / "Obra.lean").exists()


# --- Lo que se vuelca sale del almacen ----------------------------------------


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "cronologia.sqlite3")
    yield almacen
    almacen.cerrar()


def test_el_suceso_muere_lleva_su_sujeto(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra({"titulo": "Obra"})
    [ines] = almacen.guardar([Artefacto("Personaje", {"nombre": "Ines", "licencia": "plausible",
                                                     "fechas": {"nacimiento": "1551"}},
                                        id_obra=id_obra)])
    almacen.guardar([
        Artefacto("EventoEstado", {"tipo_de_evento": "muere", "sujeto": ines,
                                   "fecha_resultante": "1590", "lugar_resultante": "lug_1",
                                   "presentes": [ines]}, id_obra=id_obra, capitulo=1),
        Artefacto("EventoEstado", {"tipo_de_evento": "viaja_a", "sujeto": ines,
                                   "fecha_resultante": "1589", "lugar_resultante": "lug_1",
                                   "presentes": [ines]}, id_obra=id_obra, capitulo=1),
    ])
    sucesos = versiones.sucesos_de_la_cronologia(almacen, id_obra, 1)
    assert [(s["suceso"], s["muere"]) for s in sucesos] == [("viaja_a", None), ("muere", ines)]
    assert [s["llega"] for s in sucesos] == [ines, None], "RF-213"
    assert sucesos[0]["presentes"][0]["nacimiento"] == "1551"


class _AlmacenConCambio:
    """Un cambio del lector renombro a `per_viejo` (ahora `per_nuevo`) y a
    `lug_viejo` (ahora `lug_nuevo`): el capitulo 1 es compartido y lleva los
    `id` viejos; el 3 se reescribio y lleva los nuevos."""

    def fichas_sustituidas(self, id_obra: str, version: int) -> dict[str, str]:
        return {"per_viejo": "per_nuevo", "lug_viejo": "lug_nuevo"}

    def listar(self, tipo: str, id_obra: str, version: int) -> list[Artefacto]:
        muere = Artefacto("EventoEstado", {"tipo_de_evento": "muere", "sujeto": "per_viejo"},
                          id_obra=id_obra, capitulo=1)
        muere.id = "eve_1"
        return [muere]

    def cronologia(self, id_obra: str, version: int) -> list[dict[str, Any]]:
        return [
            {"id": "eve_1", "capitulo": 1, "lugar": "lug_viejo",
             "presentes": [{"id": "per_viejo", "nacimiento": "1551"}]},
            {"id": "eve_3", "capitulo": 3, "lugar": "lug_nuevo",
             "presentes": [{"id": "per_nuevo", "nacimiento": "1551"}]},
        ]


def test_el_volcado_lleva_cada_ficha_cambiada_por_el_lector_a_la_vigente() -> None:
    sucesos = versiones.sucesos_de_la_cronologia(_AlmacenConCambio(), "obr_1", 2)  # type: ignore[arg-type]
    assert [s["muere"] for s in sucesos] == ["per_nuevo", None]
    assert [s["lugar"] for s in sucesos] == ["lug_nuevo", "lug_nuevo"]
    presentes = [[p["id"] for p in s["presentes"]] for s in sucesos]
    assert presentes == [["per_nuevo"], ["per_nuevo"]]


# --- La puerta y la critica: el caso que solo Lean ve (RF-156) ----------------


def _cliente(tmp_path: Path) -> Iterator[TestClient]:
    """La obra limpia de la puerta, salvo que el Contable deja a los mismos
    presentes en dos lugares el mismo dia del capitulo 2."""
    app = crear_aplicacion(
        tmp_path / "lean.sqlite3", ejecutor=EjecutorDeLaPuerta(defecto="cronologia")
    )
    with TestClient(app) as cliente:
        yield cliente


@con_lean
def test_solo_lean_ve_la_contradiccion_y_la_version_no_se_publica(tmp_path: Path) -> None:
    for cliente in _cliente(tmp_path):
        id_obra = _obra_terminada(cliente)
        respuesta = cliente.post(f"/obras/{id_obra}/versiones/1/publicar")
        assert respuesta.status_code == 409
        puerta = respuesta.json()["puerta"]
        assert puerta["comprobacion_formal"] == "fallida"
        # Los cuatro programaticos no ven nada: todo lo que falla es de Lean.
        assert {f["validador"] for f in puerta["fallos"]} == {"cronologia"}
        assert all("un_solo_lugar" in f["detalle"] for f in puerta["fallos"])
        assert {f["capitulo"] for f in puerta["fallos"]} == {2}
        assert _publicaciones(cliente, id_obra) == []

        # Y vuelve al editor como critica del capitulo 2, con su evidencia.
        criticas = cliente.get(f"/obras/{id_obra}/criticas", params={"capitulo": 2}).json()
        de_lean = [c for c in criticas if "Lean no demuestra" in (c["evidencia"] or "")]
        assert len(de_lean) == len(puerta["fallos"]) >= 1, criticas
        assert {(c["dimension"], c["severidad"], c["estado"]) for c in de_lean} == {
            ("continuidad_de_estado", "bloqueante", "abierta")
        }

        # Volver a pedir la publicacion no duplica las criticas.
        assert cliente.post(f"/obras/{id_obra}/versiones/1/publicar").status_code == 409
        otra_vez = cliente.get(f"/obras/{id_obra}/criticas", params={"capitulo": 2}).json()
        assert len(otra_vez) == len(criticas)


def test_sin_lean_la_misma_version_se_publica_sin_comprobacion_formal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(demostrador, "buscar_lake", lambda: None)
    for cliente in _cliente(tmp_path):
        id_obra = _obra_terminada(cliente)
        puerta = cliente.get(f"/obras/{id_obra}/versiones/1/puerta").json()
        assert (puerta["pasa"], puerta["comprobacion_formal"]) == (True, "sin_comprobacion")
        respuesta = cliente.post(f"/obras/{id_obra}/versiones/1/publicar")
        assert respuesta.status_code == 200
        assert respuesta.json()["comprobacion_formal"] == "sin_comprobacion"
        assert len(_publicaciones(cliente, id_obra)) == 1
