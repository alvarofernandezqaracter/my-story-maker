"""El destinatario de la obra y lo que viene de su vida.

Cierre por `prueba` e `inspeccion` de RF-06 a RF-09 y RF-16. Lo que se
comprueba: que el destinatario es opcional y que si viene se rechaza nombrando
el campo anidado que falta; que cada recuerdo acaba siendo un `Recuerdo`
inmutable que ningun rol del censo escribe; que el grado de licencia `personal`
existe y los cuatro contratos de anacronismo lo eximen; y que el destinatario
llega a la ventana del Constructor de mundo y del Planificador y a la de nadie
mas. Evidencia: esta suite, el contrato de frontera publicado y los contratos
declarativos de las carpetas de tarea.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dobles import EjecutorFingido
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.esquema import TABLA_POR_TIPO
from novela.api.aplicacion import crear_aplicacion
from novela.nucleo import guion
from novela.nucleo.gobierno import QUIEN_ESCRIBE, puede_escribir
from novela.nucleo.proyecciones import MATERIALES, Peticion
from novela.tareas import CARPETA, contrato_de_tarea, contrato_de_verificacion
from novela.vocabularios import (
    LICENCIA,
    LICENCIA_EXENTA_DE_ANACRONISMO,
    PAPEL_DEL_DESTINATARIO,
    ROLES,
)

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

DESTINATARIO = {
    "nombre": "Marta",
    "edad": 9,
    "tono": "aventura luminosa",
    "dedicatoria": "Para Marta, que no le tiene miedo a los arboles",
    "rasgos": ["se sube a todo", "no suelta a su perra"],
    "recuerdos": [
        "Su perra se llama Nala y duerme a los pies de la cama",
        "Se rompio un brazo cayendose de un arbol con siete anos",
    ],
    "vetos": ["muerte de animales"],
}

# Las cuatro dimensiones de anacronismo, con la carpeta que las comprueba y la
# palabra por la que se reconoce la exencion en su predicado. Se enumeran en vez
# de deducirse: si aparece una quinta, esta prueba tiene que fallar para que
# alguien decida si tambien queda exenta.
#
# Las tres del Verificador reconocen la exencion por el grado de licencia,
# porque ven las fichas del canon. El Editor de estilo no las ve: mira el texto
# contra una lista de palabras, asi que su exencion se nombra por el
# destinatario, que es lo que si tiene delante.
CONTRATOS_DE_ANACRONISMO = [
    ("verificar", "anacronismo_material", LICENCIA_EXENTA_DE_ANACRONISMO),
    ("verificar", "anacronismo_conceptual", LICENCIA_EXENTA_DE_ANACRONISMO),
    ("verificar", "anacronismo_social_e_institucional", LICENCIA_EXENTA_DE_ANACRONISMO),
    ("editar_estilo", "anacronismo_lexico", "destinatario"),
]

ENCARGO = guion.Encargo(1, "planificar", "planificador", "capitulo", ())


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[TestClient]:
    """Dar de alta una obra la arranca, asi que al salir hay que esperarla.

    Si no, el cierre del cliente se queda colgado esperando a un hilo que
    todavia esta produciendo.
    """
    app = crear_aplicacion(tmp_path / "api.sqlite3", ejecutor=EjecutorFingido())
    with TestClient(app) as cliente:
        yield cliente
        for hilo in cliente.app.state.produccion.hilos.values():  # type: ignore[attr-defined]
            hilo.join(timeout=60)
            assert not hilo.is_alive(), "la produccion no termino"


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    tienda = abrir_almacen(tmp_path / "prueba.sqlite3")
    yield tienda
    tienda.cerrar()


def _peticion(almacen: Almacen, id_obra: str) -> Peticion:
    return Peticion(almacen=almacen, encargo=replace(ENCARGO, id_obra=id_obra))


# --- RF-06. El destinatario es opcional, pero si viene, viene entero --------


def test_una_obra_sin_destinatario_se_sigue_aceptando(cliente: TestClient) -> None:
    """La historica pelada de siempre no deja de ser valida."""
    respuesta = cliente.post("/obras", json=BRIEF)

    assert respuesta.status_code == 202


def test_un_brief_con_destinatario_completo_se_acepta(cliente: TestClient) -> None:
    respuesta = cliente.post("/obras", json=BRIEF | {"destinatario": DESTINATARIO})

    assert respuesta.status_code == 202


@pytest.mark.parametrize("campo", ["nombre", "edad", "tono", "dedicatoria"])
def test_un_destinatario_incompleto_se_rechaza_nombrando_el_campo(
    cliente: TestClient, campo: str
) -> None:
    """El rechazo da la ruta entera, no solo la hoja: `destinatario.nombre`."""
    manco = {clave: valor for clave, valor in DESTINATARIO.items() if clave != campo}

    respuesta = cliente.post("/obras", json=BRIEF | {"destinatario": manco})

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert f"destinatario.{campo}" in cuerpo["campos"]
    assert f"destinatario.{campo}" in cuerpo["detalle"]


@pytest.mark.parametrize("campo", ["rasgos", "recuerdos", "vetos"])
def test_las_listas_del_destinatario_pueden_venir_vacias(
    cliente: TestClient, campo: str
) -> None:
    """Vacio es una respuesta: no veto nada, no aporto recuerdos."""
    sin_lista = {clave: valor for clave, valor in DESTINATARIO.items() if clave != campo}

    respuesta = cliente.post("/obras", json=BRIEF | {"destinatario": sin_lista})

    assert respuesta.status_code == 202


# --- RF-07. Cada recuerdo es un `Recuerdo` ---------------------------------


def test_cada_recuerdo_del_brief_se_guarda_como_recuerdo(cliente: TestClient) -> None:
    respuesta = cliente.post("/obras", json=BRIEF | {"destinatario": DESTINATARIO})
    id_obra = respuesta.json()["id_obra"]
    almacen = cliente.app.state.produccion.almacen  # type: ignore[attr-defined]

    recuerdos = almacen.listar_recuerdos(id_obra)

    assert [r.cuerpo["texto"] for r in recuerdos] == DESTINATARIO["recuerdos"]
    assert [r.cuerpo["orden"] for r in recuerdos] == [1, 2]


def test_el_cuerpo_de_la_obra_no_duplica_los_recuerdos(cliente: TestClient) -> None:
    """La capa Obra referencia la capa Mundo por `id` y nunca la duplica."""
    respuesta = cliente.post("/obras", json=BRIEF | {"destinatario": DESTINATARIO})
    id_obra = respuesta.json()["id_obra"]
    almacen = cliente.app.state.produccion.almacen  # type: ignore[attr-defined]

    obra = almacen.leer_obra(id_obra)

    assert obra is not None
    assert obra.cuerpo["destinatario"]["nombre"] == "Marta"
    assert "recuerdos" not in obra.cuerpo["destinatario"]


def test_ningun_rol_del_censo_escribe_un_recuerdo() -> None:
    """Si se abriera esta puerta, el invariante de la `Fuente` dejaria de
    significar nada: se podria colar un dato sin respaldo llamandolo recuerdo."""
    assert QUIEN_ESCRIBE["Recuerdo"] == frozenset()
    assert not any(puede_escribir(rol, "Recuerdo") for rol in ROLES)


def test_un_recuerdo_es_inmutable() -> None:
    assert TABLA_POR_TIPO["Recuerdo"].inmutable


# --- RF-08. La licencia `personal` y la exencion de anacronismo ------------


def test_personal_es_un_grado_de_licencia() -> None:
    assert LICENCIA_EXENTA_DE_ANACRONISMO in LICENCIA


@pytest.mark.parametrize(("tarea", "dimension", "marca"), CONTRATOS_DE_ANACRONISMO)
def test_los_cuatro_contratos_de_anacronismo_eximen_lo_personal(
    tarea: str, dimension: str, marca: str
) -> None:
    """Sin esta exencion, el nombre real del destinatario saldria como defecto
    en cada capitulo y la obra se atascaria corrigiendo el regalo."""
    contrato = contrato_de_verificacion(tarea, dimension)

    assert marca in contrato["predicado"]


def test_las_dimensiones_de_anacronismo_enumeradas_son_todas_las_que_hay() -> None:
    declaradas = {
        ruta.stem
        for ruta in CARPETA.glob("*/contratos/*.toml")
        if ruta.stem.startswith("anacronismo")
    }

    assert declaradas == {dimension for _, dimension, _ in CONTRATOS_DE_ANACRONISMO}


# --- RF-09. El papel lo decide el Planificador -----------------------------


def test_el_papel_del_destinatario_es_vocabulario_cerrado() -> None:
    assert PAPEL_DEL_DESTINATARIO == ("protagonista", "secundario", "testigo", "narrador")


def test_el_prompt_del_planificador_le_encarga_escribir_el_papel() -> None:
    prompt = (CARPETA / "planificar" / "prompt.md").read_text(encoding="utf-8")

    assert "papel_del_destinatario" in prompt
    for papel in PAPEL_DEL_DESTINATARIO:
        assert papel in prompt


def test_el_brief_no_deja_elegir_el_papel(cliente: TestClient) -> None:
    """No es un campo del editor: si lo manda, no se guarda como suyo."""
    respuesta = cliente.post(
        "/obras",
        json=BRIEF | {"destinatario": DESTINATARIO | {"papel": "protagonista"}},
    )
    id_obra = respuesta.json()["id_obra"]
    almacen = cliente.app.state.produccion.almacen  # type: ignore[attr-defined]
    obra = almacen.leer_obra(id_obra)

    assert obra is not None
    assert "papel" not in obra.cuerpo["destinatario"]


# --- RF-16. Quien ve al destinatario y quien no ----------------------------

PASOS_QUE_LO_VEN = {"planificar", "poblar_mundo"}


def test_solo_dos_pasos_del_guion_reciben_al_destinatario() -> None:
    con_destinatario = {
        paso.tarea for paso in guion.PASOS if "destinatario" in paso.proyeccion
    } | {
        nombre
        for nombre, paso in guion.FUERA_DEL_GUION.items()
        if "destinatario" in paso.proyeccion
    }

    assert con_destinatario == PASOS_QUE_LO_VEN


@pytest.mark.parametrize("tarea", sorted(PASOS_QUE_LO_VEN))
def test_los_dos_contratos_declaran_el_destinatario_como_entrada(tarea: str) -> None:
    entrada = contrato_de_tarea(tarea)["entrada"]

    assert "destinatario" in entrada
    assert "recuerdos_del_destinatario" in entrada


def test_la_obra_y_la_premisa_no_llevan_al_destinatario_dentro(almacen: Almacen) -> None:
    """Colarlo ahi lo haria llegar a todo rol que pida la obra y la premisa."""
    id_obra = almacen.crear_obra(BRIEF | {"destinatario": DESTINATARIO})

    obra_y_premisa = MATERIALES["obra_y_premisa"](_peticion(almacen, id_obra))

    assert obra_y_premisa["titulo"] == BRIEF["titulo"]
    assert "destinatario" not in obra_y_premisa


def test_el_destinatario_se_pide_por_su_nombre(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF | {"destinatario": DESTINATARIO})

    destinatario = MATERIALES["destinatario"](_peticion(almacen, id_obra))

    assert destinatario["nombre"] == "Marta"


def test_el_canon_no_arrastra_los_recuerdos(almacen: Almacen) -> None:
    """El `Recuerdo` es materia prima, no ficha: tiene material propio."""
    id_obra = almacen.crear_obra(BRIEF, ["Su perra se llama Nala"])
    peticion = _peticion(almacen, id_obra)

    canon = MATERIALES["canon"](peticion)
    recuerdos = MATERIALES["recuerdos_del_destinatario"](peticion)

    assert [ficha for ficha in canon if ficha["tipo"] == "Recuerdo"] == []
    assert [r["texto"] for r in recuerdos] == ["Su perra se llama Nala"]


def test_el_canon_no_arrastra_las_fuentes(almacen: Almacen) -> None:
    """SPEC1 RF-217: las fuentes crecen por capitulo; el canon no."""
    id_obra = almacen.crear_obra(BRIEF)
    almacen.guardar([
        Artefacto("Fuente", {"cita": "Ordenanzas, 1558", "que_afirma": "x"},
                  id_obra=id_obra, capitulo=3),
        Artefacto("Practica", {"nombre": "la copia a destajo", "licencia": "plausible"},
                  id_obra=id_obra),
    ])
    peticion = _peticion(almacen, id_obra)

    canon = MATERIALES["canon"](peticion)
    fuentes = MATERIALES["fuentes_recogidas"](peticion)

    assert [ficha["tipo"] for ficha in canon] == ["Practica"]
    assert [f["cita"] for f in fuentes] == ["Ordenanzas, 1558"]


def test_el_contrato_del_lexico_ve_al_destinatario() -> None:
    """Es lo que le permite no senalar un nombre de hoy como palabra vetada."""
    contrato = contrato_de_verificacion("editar_estilo", "anacronismo_lexico")

    assert "destinatario" in contrato["proyeccion_minima"]
