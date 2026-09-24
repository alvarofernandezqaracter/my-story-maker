"""SPEC1 4.15: los validadores programaticos y la puerta de publicacion.

Metodo: `prueba`, sin gastar. Cada validador tiene un caso que pasa y otro que
falla; el hook `validar_capitulo` se alimenta con la entrada que le daria Claude
Code; y una obra entera corre con un ejecutor fingido al que se le siembra un
defecto por caso: la version no se publica, la respuesta dice que fallo y en que
capitulo, y la misma obra sin el defecto se publica (criterio 10 de §10).
Evidencia: los codigos y los cuerpos de la API, y el registro de publicaciones.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dobles import EjecutorFingido
from novela import ganchos, validadores
from novela.almacen import Artefacto
from novela.api.aplicacion import crear_aplicacion
from novela.demostrador import buscar_lake
from novela.ejecutor import EjecutorDeSubagentes, veredicto_de_los_ganchos
from novela.nucleo import guion
from novela.nucleo.caminante import Resultado
from novela.nucleo.guion import Encargo, GuionInvalido
from novela.nucleo.proyecciones import Ventana
from novela.vocabularios import VALIDADOR_DE_LA_PUERTA

# --- Cada validador, un caso que pasa y otro que falla ------------------------


def test_palabras_y_longitud() -> None:
    assert validadores.palabras("Ines cruzo, sin prisa, la plaza.") == 6
    assert validadores.longitud_fuera_de_rango(1_500, 1_000, 4_000) is None
    assert "minimo" in (validadores.longitud_fuera_de_rango(200, 1_000, 4_000) or "")
    assert "maximo" in (validadores.longitud_fuera_de_rango(5_000, 1_000, 4_000) or "")


def test_el_rango_de_longitud_esta_en_el_guion() -> None:
    minimo, maximo = guion.PALABRAS_POR_CAPITULO
    assert 1 <= minimo <= maximo
    for roto in (
        {},
        {"capitulo": {"palabras_minimas": 1_000}},
        {"capitulo": {"palabras_minimas": 0, "palabras_maximas": 10}},
        {"capitulo": {"palabras_minimas": 5_000, "palabras_maximas": 4_000}},
    ):
        with pytest.raises(GuionInvalido):
            guion._palabras_por_capitulo(roto)


def test_el_esquema_de_una_tarea() -> None:
    esquema = {"tipo": "Borrador", "cuerpo": {"texto": "", "unidad": "", "cumple": []}}
    lista = [esquema, {"tipo": "Mencion", "cuerpo": {"hecho": "", "capitulo": 1}}]
    completo = {"texto": "x", "unidad": "esc_1", "cumple": []}
    assert validadores.campos_que_faltan(esquema, "Borrador", completo) == []
    assert validadores.campos_que_faltan(esquema, "Borrador", {"texto": "x"}) == [
        "cumple",
        "unidad",
    ]
    assert validadores.campos_que_faltan(lista, "Mencion", {"hecho": "per_1"}) == ["capitulo"]
    assert validadores.campos_que_faltan(esquema, "Parrafo", {}) is None


NOMBRES = ("Ines de Salcedo", "Pedro", "Sevilla", "Marta")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Inés cruzo la plaza.", [("Inés", "Ines")]),
        ("La viuda de Salzedo llego tarde.", [("Salzedo", "Salcedo")]),
        ("Llegaron a Sevillla de noche.", [("Sevillla", "Sevilla")]),
        ("Ines de Salcedo y Pedro llegaron a Sevilla.", []),
        # «Pero» esta a una letra de «Pedro», y es una palabra corriente (D-56).
        ("Pero nadie lo supo.", []),
        # Lo que tambien sale en minuscula no se toma por nombre.
        ("Marte brillaba. Nadie miraba a marte.", []),
        ("Martha llego sola.", []),
    ],
)
def test_nombres_mal_escritos(texto: str, esperado: list[tuple[str, str]]) -> None:
    assert validadores.nombres_mal_escritos(texto, NOMBRES) == esperado


def test_el_nombre_aparece_tal_cual() -> None:
    assert validadores.aparece_tal_cual("Marta", ["Para Marta, con carino."])
    assert not validadores.aparece_tal_cual("Marta", ["Para Martina."])


# --- El hook de nombres (RF-145) ----------------------------------------------


def _entrega(texto: str) -> str:
    return json.dumps(
        {
            "artefactos": [
                {
                    "tipo": "Borrador",
                    "cuerpo": {"texto": texto, "unidad": "esc_1", "cumple": ["objetivo"]},
                }
            ]
        },
        ensure_ascii=False,
    )


def _hook(texto: str, nombres: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    monkeypatch.setenv(ganchos.VARIABLE_DE_VETOS, "[]")
    monkeypatch.setenv(ganchos.VARIABLE_DE_RESERVA, "4000")
    monkeypatch.setenv(ganchos.VARIABLE_DE_NOMBRES, json.dumps(nombres, ensure_ascii=False))
    entrada = json.dumps({"last_assistant_message": texto, "stop_hook_active": False})
    codigo, _, motivo = ganchos.principal(["validar_capitulo", "redactar"], entrada)
    return codigo, motivo


def test_el_hook_bloquea_un_nombre_mal_escrito(monkeypatch: pytest.MonkeyPatch) -> None:
    codigo, motivo = _hook(_entrega("Inés cruzo la plaza."), list(NOMBRES), monkeypatch)
    assert codigo == ganchos.SALIDA_BLOQUEA
    assert "«Inés»" in motivo and "«Ines»" in motivo


def test_el_hook_deja_pasar_los_nombres_bien_escritos(monkeypatch: pytest.MonkeyPatch) -> None:
    codigo, _ = _hook(_entrega("Pero Ines cruzo Sevilla."), list(NOMBRES), monkeypatch)
    assert codigo == ganchos.SALIDA_PASA


def test_el_ejecutor_repite_la_comprobacion_de_nombres() -> None:
    """RF-126: lo que no pasa al final lo juzga el ejecutor con la misma funcion."""
    encargo = guion.expandir(guion.paso(3), id_obra="obr_1", capitulo=1, escenas=("esc_1",))[0]
    registro = veredicto_de_los_ganchos(
        encargo, _entrega("Inés cruzo."), (), [], nombres=NOMBRES
    )
    assert registro is not None
    forma = next(f for f in registro["final"] if f["gancho"] == "validar_capitulo")
    assert not forma["pasa"] and "Inés" in forma["motivos"][0]


def test_los_nombres_viajan_por_el_entorno_y_no_por_la_ventana() -> None:
    encargo = guion.expandir(guion.paso(3), id_obra="obr_1", capitulo=1, escenas=("esc_1",))[0]
    ventana = Ventana(materiales={}, texto="{}", tokens=1, nombres=("Marta",))
    entorno = EjecutorDeSubagentes()._entorno(encargo, ventana)
    assert entorno is not None
    assert json.loads(entorno[ganchos.VARIABLE_DE_NOMBRES]) == ["Marta"]
    assert "Marta" not in ventana.texto


# --- La puerta, con una obra entera ------------------------------------------

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "arcos": [],
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 2,
    "destinatario": {
        "nombre": "Marta",
        "edad": 9,
        "tono": "aventura luminosa",
        "dedicatoria": "Para Marta",
        "rasgos": [],
        "recuerdos": ["su perra Nala le robaba los calcetines"],
        "vetos": [],
    },
}

PROSA = "Marta miro la prensa. " + "tinta " * 400

NALA = {
    "nombre": "Nala",
    "tratamientos": [],
    "estatus_ontologico": "ficticio",
    "licencia": "personal",
    "fechas": {"nacimiento": "1580"},
    "extraccion_social": "perra de la casa",
    "oficio": "ninguno",
    "rasgos_fisicos": ["orejas caidas"],
    "voz": {"lexico": [], "muletillas": [], "temas": []},
    "motivacion_dominante": "robar calcetines",
    "herida": "ninguna",
    "arco_declarado": "ninguno",
    "recuerdo": "rcd_1",
}


@dataclass
class EjecutorDeLaPuerta:
    """El fingido de siempre con la perra del destinatario en la biblia, y un
    defecto sembrado a eleccion en un capitulo."""

    defecto: str | None = None
    en_capitulo: int = 2
    interno: EjecutorFingido = field(
        default_factory=lambda: EjecutorFingido(texto_cosido=PROSA)
    )

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        resultado = self.interno.ejecutar(encargo, ventana)
        aqui = encargo.capitulo == self.en_capitulo
        if encargo.tarea == "poblar_mundo":
            resultado.artefactos.append(Artefacto("Personaje", dict(NALA)))
        for artefacto in resultado.artefactos:
            if encargo.tarea == "editar_estilo" and artefacto.tipo == "Borrador" and aqui:
                if self.defecto == "longitud":
                    artefacto.cuerpo = artefacto.cuerpo | {"texto": "Poco."}
                if self.defecto == "nombres":
                    artefacto.cuerpo = artefacto.cuerpo | {"texto": "Inés llego. " + PROSA}
            if self.defecto == "esquema" and artefacto.tipo == "Escena" and aqui:
                artefacto.cuerpo = {
                    k: v for k, v in artefacto.cuerpo.items() if k != "focalizacion"
                }
        if self.defecto == "cronologia" and encargo.tarea == "plegar" and aqui:
            # El Contable deja a los mismos presentes en otro lugar el mismo dia:
            # nada que vean los cuatro programaticos, y Lean si (SPEC1 RF-156).
            [evento] = [a for a in resultado.artefactos if a.tipo == "EventoEstado"]
            resultado.artefactos.append(
                Artefacto(
                    "EventoEstado",
                    evento.cuerpo | {"objeto": "lug_0009", "lugar_resultante": "lug_0009"},
                    capitulo=evento.capitulo,
                )
            )
        if self.defecto == "elementos_personalizados" and encargo.tarea == "destilar":
            nala = [
                fila["id"]
                for fila in ventana.materiales.get("indice_de_la_biblia") or []
                if fila["nombre"] == "Nala"
            ]
            resultado.artefactos = [
                a
                for a in resultado.artefactos
                if not (a.tipo == "Mencion" and a.cuerpo.get("hecho") in nala)
            ]
        return resultado


def _cliente(tmp_path: Path, ejecutor: EjecutorDeLaPuerta) -> Iterator[TestClient]:
    app = crear_aplicacion(tmp_path / "puerta.sqlite3", ejecutor=ejecutor)
    with TestClient(app) as cliente:
        yield cliente


def _obra_terminada(cliente: TestClient) -> str:
    id_obra = str(cliente.post("/obras", json=BRIEF).json()["id_obra"])
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=120)
    assert not hilo.is_alive()
    return id_obra


def _publicaciones(cliente: TestClient, id_obra: str) -> list[Any]:
    produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
    return list(
        produccion.almacen._lector.execute(
            "SELECT numero FROM publicacion_de_version WHERE id_obra = ?", (id_obra,)
        ).fetchall()
    )


def test_una_version_limpia_pasa_la_puerta_y_se_publica(tmp_path: Path) -> None:
    for cliente in _cliente(tmp_path, EjecutorDeLaPuerta()):
        id_obra = _obra_terminada(cliente)
        puerta = cliente.get(f"/obras/{id_obra}/versiones/1/puerta").json()
        assert (puerta["pasa"], puerta["terminada"], puerta["fallos"]) == (True, True, [])
        assert cliente.post(f"/obras/{id_obra}/versiones/1/publicar").status_code == 200
        assert len(_publicaciones(cliente, id_obra)) == 1


@pytest.mark.parametrize("defecto", VALIDADOR_DE_LA_PUERTA)
def test_una_version_con_un_fallo_no_se_publica_y_dice_cual_y_donde(
    tmp_path: Path, defecto: str
) -> None:
    if defecto == "cronologia" and buscar_lake() is None:
        pytest.skip("la cronologia la comprueba Lean, y Lean no esta instalado aqui")
    for cliente in _cliente(tmp_path, EjecutorDeLaPuerta(defecto=defecto)):
        id_obra = _obra_terminada(cliente)
        respuesta = cliente.post(f"/obras/{id_obra}/versiones/1/publicar")
        assert respuesta.status_code == 409
        cuerpo = respuesta.json()
        assert "puerta" in cuerpo["detail"]
        fallos = cuerpo["puerta"]["fallos"]
        assert cuerpo["puerta"]["pasa"] is False
        assert {f["validador"] for f in fallos} == {defecto}, fallos
        capitulo_esperado = None if defecto == "elementos_personalizados" else 2
        assert all(f["capitulo"] == capitulo_esperado for f in fallos), fallos
        # No se publica nada, y la puerta servida aparte dice lo mismo.
        assert _publicaciones(cliente, id_obra) == []
        assert cliente.get(f"/obras/{id_obra}").json()["version_publicada"] is None
        servida = cliente.get(f"/obras/{id_obra}/versiones/1/puerta").json()
        assert servida == cuerpo["puerta"]


def test_el_nombre_del_destinatario_tiene_que_aparecer(tmp_path: Path) -> None:
    ejecutor = EjecutorDeLaPuerta()
    ejecutor.interno.texto_cosido = "La prensa. " + "tinta " * 400
    for cliente in _cliente(tmp_path, ejecutor):
        id_obra = _obra_terminada(cliente)
        fallos = cliente.get(f"/obras/{id_obra}/versiones/1/puerta").json()["fallos"]
        assert [(f["validador"], f["capitulo"]) for f in fallos] == [("nombres", None)]
        assert "Marta" in fallos[0]["detalle"]


def test_la_puerta_de_una_version_que_no_existe_es_un_404(tmp_path: Path) -> None:
    for cliente in _cliente(tmp_path, EjecutorDeLaPuerta()):
        id_obra = _obra_terminada(cliente)
        assert cliente.get(f"/obras/{id_obra}/versiones/9/puerta").status_code == 404
