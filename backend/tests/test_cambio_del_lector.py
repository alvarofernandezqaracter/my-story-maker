"""SPEC1 4.18: el cambio del lector y el PDF.

Metodo: `prueba`. Una obra de tres capitulos corre entera con un ejecutor
fingido que firma la prosa con la version en curso y que anota las menciones de
la biblia solo en los capitulos 1 y 3. Se cambia el nombre de un hecho y se
comprueba que nace la version 2 con esos dos capitulos, que el 2 se comparte
—las mismas filas— y que la version 1 sirve exactamente lo mismo que antes
(RF-179). Se siembran ademas los rechazos, una caida a medias de un capitulo
suelto y la descarga del PDF. Evidencia: las respuestas de la API por version,
las filas del almacen y los bytes del PDF.
"""

import re
import sqlite3
import zlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen, VersionNoAdmitida
from novela.almacen.artefactos import HechoSinMenciones, abrir_almacen
from novela.api.aplicacion import crear_aplicacion
from novela.api.pdf import a_latin1
from novela.nucleo import versiones
from novela.nucleo.caminante import Caminante, Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana

BRIEF: dict[str, Any] = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 3,
    "destinatario": {
        "nombre": "Lucía",
        "edad": 40,
        "tono": "calido",
        "dedicatoria": "Para Lucía, que me enseñó a leer",
        "rasgos": [],
        "recuerdos": [],
        "vetos": [],
    },
}

PROSA_DE_ESCENA = "Version cosida de la escena para Lucía. " + "tinta " * 400
# Los capitulos en que el fingido anota las menciones de la biblia.
CAPITULOS_CON_MENCION = (1, 3)


@dataclass
class EjecutorDelLector:
    """El fingido de siempre, que firma la prosa y solo menciona la biblia en
    los capitulos de `con_mencion`. `sin_mencion` son nombres que no menciona
    nunca. `caida` tumba el proceso al llegar a esa tarea de ese capitulo."""

    firma: str = "v1"
    con_mencion: tuple[int, ...] = CAPITULOS_CON_MENCION
    sin_mencion: tuple[str, ...] = ()
    caida: tuple[str, int] | None = None
    interno: EjecutorFingido = field(
        default_factory=lambda: EjecutorFingido(texto_cosido=PROSA_DE_ESCENA)
    )

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        if self.caida == (encargo.tarea, encargo.capitulo):
            self.caida = None
            raise Caida(f"se cae la maquina en {encargo.tarea}")
        resultado = self.interno.ejecutar(encargo, ventana)
        nombres = {
            fila["id"]: fila["nombre"]
            for fila in ventana.materiales.get("indice_de_la_biblia") or []
        }
        conservados = []
        for artefacto in resultado.artefactos:
            if artefacto.tipo == "Mencion" and (
                encargo.capitulo not in self.con_mencion
                or nombres.get(artefacto.cuerpo["hecho"]) in self.sin_mencion
            ):
                continue
            if artefacto.tipo == "Borrador":
                artefacto.cuerpo = artefacto.cuerpo | {
                    "texto": f"[{self.firma}] {artefacto.cuerpo.get('texto', '')}"
                }
            conservados.append(artefacto)
        resultado.artefactos = conservados
        return resultado


class Caida(BaseException):
    """El proceso muere: nada la recoge."""


@pytest.fixture
def ejecutor() -> EjecutorDelLector:
    return EjecutorDelLector()


@pytest.fixture
def cliente(tmp_path: Path, ejecutor: EjecutorDelLector) -> Iterator[TestClient]:
    app = crear_aplicacion(tmp_path / "lector.sqlite3", ejecutor=ejecutor)
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


def _hecho(cliente: TestClient, id_obra: str, tipo: str, version: int = 1) -> dict[str, Any]:
    hechos = cliente.get(f"/obras/{id_obra}/hechos?tipo={tipo}&version={version}").json()
    assert len(hechos) == 1
    return dict(hechos[0])


def _lo_que_sirve(cliente: TestClient, id_obra: str, version: int) -> dict[str, Any]:
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


# --- RF-170 a RF-175, RF-179: solo los capitulos que lo mencionan ----------


def test_el_cambio_reescribe_solo_los_capitulos_que_mencionan_el_hecho(
    cliente: TestClient, ejecutor: EjecutorDelLector
) -> None:
    id_obra = _obra_terminada(cliente)
    lugar = _hecho(cliente, id_obra, "Lugar")
    assert lugar["capitulos"] == [1, 3]
    antes = _lo_que_sirve(cliente, id_obra, 1)

    ejecutor.firma = "v2"
    llamadas_antes = len(ejecutor.interno.llamadas)
    respuesta = cliente.post(
        f"/obras/{id_obra}/cambios", json={"hecho": lugar["id"], "valor": "Hispalis"}
    )
    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json()["version"] == 2
    assert respuesta.json()["capitulos_cambiados"] == [1, 3]
    _esperar(cliente, id_obra)

    # Solo se planificaron los capitulos 1 y 3, con la ficha nueva en el canon.
    nuevas = list(zip(ejecutor.interno.llamadas, ejecutor.interno.ventanas, strict=True))[
        llamadas_antes:
    ]
    planificados = [(e.capitulo, v) for e, v in nuevas if e.tarea == "planificar"]
    assert [capitulo for capitulo, _ in planificados] == [1, 3]
    for _, ventana in planificados:
        nombres = [f.get("nombre") for f in ventana.materiales["canon"]]
        assert "Hispalis" in nombres and "Sevilla" not in nombres

    versiones_servidas = cliente.get(f"/obras/{id_obra}/versiones").json()
    assert versiones_servidas[0]["cambio"] is None
    segunda = versiones_servidas[1]
    assert (segunda["base"], segunda["capitulos_cambiados"], segunda["terminada"]) == (
        1, [1, 3], True
    )
    assert segunda["cambio"] == {
        "hecho": lugar["id"], "tipo": "Lugar", "anterior": "Sevilla", "nuevo": "Hispalis"
    }

    # La 2 comparte el capitulo 2 —las mismas filas— y reescribe el 1 y el 3.
    texto = {
        u["capitulo"]: u["texto"]
        for u in cliente.get(f"/obras/{id_obra}/manuscrito?version=2").json()["unidades"]
    }
    assert texto[1].startswith("[v2]") and texto[3].startswith("[v2]")
    assert texto[2].startswith("[v1]")
    escenas = {
        v: [e["id"] for e in cliente.get(f"/obras/{id_obra}/capitulos/2?version={v}").json()[
            "escenas"
        ]]
        for v in (1, 2)
    }
    assert escenas[1] == escenas[2]

    # El hecho se versiona: la 2 ve el nombre nuevo y la 1 el viejo.
    nuevo = _hecho(cliente, id_obra, "Lugar", version=2)
    assert nuevo["nombre"] == "Hispalis" and nuevo["id"] != lugar["id"]
    assert nuevo["capitulos"] == [1, 3]
    assert _lo_que_sirve(cliente, id_obra, 1) == antes

    # Se publica por la puerta, como cualquier otra version.
    publicada = cliente.post(f"/obras/{id_obra}/versiones/2/publicar")
    assert publicada.status_code == 200, publicada.text


def test_la_ficha_nueva_la_escribe_el_backend_y_la_vieja_queda_relevada(
    cliente: TestClient,
) -> None:
    id_obra = _obra_terminada(cliente)
    lugar = _hecho(cliente, id_obra, "Lugar")
    cliente.post(f"/obras/{id_obra}/cambios", json={"hecho": lugar["id"], "valor": "Hispalis"})
    _esperar(cliente, id_obra)
    almacen: Almacen = cliente.app.state.produccion.almacen  # type: ignore[attr-defined]
    vieja = almacen.leer("Lugar", lugar["id"], incluir_caducados=True)
    assert vieja is not None and vieja.relevado_por == 2 and vieja.caducado_en is not None
    nueva = [
        f for f in almacen.listar("Lugar", id_obra) if f.cuerpo.get("nombre") == "Hispalis"
    ]
    assert len(nueva) == 1
    assert nueva[0].procedencia_rol is None
    assert nueva[0].version_de_obra == 2
    assert nueva[0].cuerpo["sustituye"] == lugar["id"]


def test_la_cronologia_de_un_capitulo_compartido_resuelve_la_ficha_sustituta(
    cliente: TestClient,
) -> None:
    id_obra = _obra_terminada(cliente)
    persona = _hecho(cliente, id_obra, "Personaje")
    respuesta = cliente.post(
        f"/obras/{id_obra}/cambios", json={"hecho": persona["id"], "valor": "Ines de Guzman"}
    )
    assert respuesta.status_code == 202
    _esperar(cliente, id_obra)

    def nombres(version: int) -> set[str | None]:
        cronologia = cliente.get(f"/obras/{id_obra}/cronologia?version={version}").json()
        return {
            p["nombre"]
            for s in cronologia["sucesos"]
            if s["origen"] == "evento_de_estado"
            for p in s["presentes"]
        }

    assert nombres(1) == {"Ines de Salcedo"}
    assert nombres(2) == {"Ines de Guzman"}


# --- RF-170, RF-171: los rechazos no crean nada ----------------------------


def test_los_rechazos_no_abren_ninguna_version(tmp_path: Path) -> None:
    ejecutor = EjecutorDelLector(sin_mencion=("Sevilla",))
    app = crear_aplicacion(tmp_path / "rechazos.sqlite3", ejecutor=ejecutor)
    with TestClient(app) as cliente:
        id_obra = _obra_terminada(cliente)
        lugar = _hecho(cliente, id_obra, "Lugar")
        persona = _hecho(cliente, id_obra, "Personaje")
        assert lugar["capitulos"] == []

        def cambio(hecho: str, valor: str) -> int:
            return cliente.post(
                f"/obras/{id_obra}/cambios", json={"hecho": hecho, "valor": valor}
            ).status_code

        assert cambio("lug_00000000", "Hispalis") == 404
        assert cambio(persona["id"], "Ines de Salcedo") == 422
        assert cambio(persona["id"], "   ") == 422
        sin_menciones = cliente.post(
            f"/obras/{id_obra}/cambios", json={"hecho": lugar["id"], "valor": "Hispalis"}
        )
        assert sin_menciones.status_code == 409
        assert "no hay nada que reescribir" in sin_menciones.json()["detail"]
        assert len(cliente.get(f"/obras/{id_obra}/versiones").json()) == 1
        assert _hecho(cliente, id_obra, "Lugar")["nombre"] == "Sevilla"


def test_una_version_sin_terminar_no_admite_el_cambio(tmp_path: Path) -> None:
    almacen = abrir_almacen(tmp_path / "sin_terminar.sqlite3")
    try:
        id_obra = almacen.crear_obra(BRIEF | {"destinatario": None})
        caminante = Caminante(almacen, EjecutorDelLector(), catalogo=CatalogoFingido())
        caminante.caminar_obra(id_obra, 3)
        persona = almacen.listar("Personaje", id_obra)[0]
        almacen.abrir_version(id_obra, 2, 3)  # rehacer: la 2 aun no ha terminado
        with pytest.raises(VersionNoAdmitida) as rechazo:
            versiones.cambiar_hecho(almacen, None, id_obra, persona.id, "Ines de Guzman")
        assert not isinstance(rechazo.value, HechoSinMenciones)
        assert len(almacen.listar_versiones(id_obra)) == 2
    finally:
        almacen.cerrar()


# --- RF-176: una caida a medias de un capitulo suelto ----------------------


def test_una_caida_en_un_capitulo_suelto_no_deja_nada_suyo_ni_toca_los_cerrados(
    tmp_path: Path,
) -> None:
    almacen = abrir_almacen(tmp_path / "caida.sqlite3")
    try:
        id_obra = almacen.crear_obra(BRIEF | {"destinatario": None})
        ejecutor = EjecutorDelLector()
        Caminante(almacen, ejecutor, catalogo=CatalogoFingido()).caminar_obra(id_obra, 3)
        escenas_del_2 = [e.id for e in almacen.listar("Escena", id_obra, capitulo=2)]
        lugar = almacen.listar("Lugar", id_obra)[0]

        _, capitulos = versiones.cambiar_hecho(almacen, None, id_obra, lugar.id, "Hispalis")
        assert capitulos == [1, 3]
        ejecutor.firma = "v2"
        ejecutor.caida = ("redactar", 3)
        with pytest.raises(Caida):
            Caminante(almacen, ejecutor, catalogo=CatalogoFingido()).caminar_obra(id_obra, 3)
        assert almacen.listar("Escena", id_obra, capitulo=3), "la caida deja el 3 a medias"

        caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())
        assert caminante.volver_al_punto_de_guardado(id_obra) == 2
        assert almacen.listar("Escena", id_obra, capitulo=3) == []
        assert [e.id for e in almacen.listar("Escena", id_obra, capitulo=2)] == escenas_del_2
        assert almacen.capitulos_cerrados(id_obra) == [1, 2]

        caminante.caminar_obra(id_obra, 3)
        for numero in (1, 2, 3):
            assert len(almacen.listar("Capitulo", id_obra, capitulo=numero)) == 1
            assert len(almacen.eventos_del_capitulo(id_obra, numero)) == 1
            assert len(almacen.listar("ResumenCapitulo", id_obra, capitulo=numero)) == 1
        assert almacen.leer_version(id_obra, 2)["terminada_en"] is not None  # type: ignore[index]
        assert not almacen.trazas_abiertas(id_obra)
        textos = {b.capitulo: b.cuerpo["texto"] for b in almacen.manuscrito_aceptado(id_obra)}
        assert textos[2].startswith("[v1]") and textos[3].startswith("[v2]")
    finally:
        almacen.cerrar()


# --- RF-173: el registro del cambio es de solo anadir ----------------------


def test_el_registro_del_cambio_no_se_borra_ni_se_cambia(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)
    lugar = _hecho(cliente, id_obra, "Lugar")
    cliente.post(f"/obras/{id_obra}/cambios", json={"hecho": lugar["id"], "valor": "Hispalis"})
    _esperar(cliente, id_obra)
    ruta = cliente.app.state.produccion.almacen.ruta  # type: ignore[attr-defined]
    conexion = sqlite3.connect(ruta)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE cambio_del_lector SET nuevo = 'otro'")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM cambio_del_lector")
    finally:
        conexion.close()


# --- RF-177: la portada en la ficha ---------------------------------------


def test_la_ficha_trae_el_destinatario_y_la_dedicatoria(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)
    ficha = cliente.get(f"/obras/{id_obra}").json()
    assert ficha["destinatario"] == "Lucía"
    assert ficha["dedicatoria"] == "Para Lucía, que me enseñó a leer"


# --- RF-178: el PDF, al vuelo y sin tocar el disco ------------------------


def _texto_del_pdf(contenido: bytes) -> bytes:
    """Lo que pintan las paginas: los flujos del PDF, descomprimidos."""
    texto = b""
    for flujo in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", contenido, re.S):
        try:
            texto += zlib.decompress(flujo)
        except zlib.error:
            texto += flujo
    return texto


def test_el_pdf_sale_con_portada_indice_y_acentos_y_no_toca_el_disco(
    cliente: TestClient, tmp_path: Path
) -> None:
    id_obra = _obra_terminada(cliente)
    antes = sorted(p.name for p in tmp_path.iterdir())
    respuesta = cliente.get(f"/obras/{id_obra}/pdf")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.headers["content-disposition"].startswith("attachment;")
    assert respuesta.content.startswith(b"%PDF")
    texto = _texto_del_pdf(respuesta.content)
    for esperado in ("Para Lucía", "que me enseñó a leer", "Índice", "Capítulo 3"):
        assert esperado.encode("latin-1") in texto, esperado
    assert sorted(p.name for p in tmp_path.iterdir()) == antes
    assert cliente.get(f"/obras/{id_obra}/pdf?version=9").status_code == 404


def test_lo_que_latin1_no_tiene_se_sustituye_y_lo_demas_sale_tal_cual() -> None:
    assert a_latin1("—¿Quién? «Ñandú»… “sí”") == "-¿Quién? «Ñandú»... \"sí\""
    assert a_latin1("é") == "é"
    assert a_latin1("☃") == "?"
