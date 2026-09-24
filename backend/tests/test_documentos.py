"""Los entregables del ciclo tambien se verifican (validators.md 11).

Metodo: `analisis`. Un documento se comprueba mirando si dice lo mismo que los
demas y lo mismo que el sistema. Lo que sigue son los cotejos de esa seccion que
se pueden hacer sin leer: si uno falla, el defecto esta en el documento, no en
el codigo.
"""

import unicodedata
from pathlib import Path

import pytest

from novela.tareas import contrato_de_verificacion, dimensiones_de
from novela.vocabularios import (
    DIMENSIONES,
    LICENCIA,
    ROLES,
    TIPOS_DE_LA_CAPA_MUNDO,
    TIPOS_DE_TAREA,
)

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"
AGENTES = Path(__file__).resolve().parent.parent.parent / "AGENTS.md"


@pytest.fixture(scope="module")
def documentos() -> dict[str, str]:
    return {
        nombre: (DOCS / f"{nombre}.md").read_text(encoding="utf-8")
        for nombre in ("definitions", "architecture", "validators", "domain-knowledge")
    } | {"agents": AGENTES.read_text(encoding="utf-8")}


def _sin_tildes(texto: str) -> str:
    """Compara al margen de las tildes: el codigo no las lleva y la prosa si."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(letra for letra in descompuesto if not unicodedata.combining(letra))


def _en_prosa(identificador: str) -> str:
    """De `integridad_de_pov` a «integridad de pov», como se escribe en prosa."""
    return identificador.replace("_", " ")


# --- Las listas dicen lo mismo ---------------------------------------------


@pytest.mark.parametrize("dimension", DIMENSIONES)
def test_toda_dimension_existe_en_definitions(
    documentos: dict[str, str], dimension: str
) -> None:
    """Una dimension que solo esta en un sitio es un error de ese sitio."""
    assert _en_prosa(dimension) in _sin_tildes(documentos["definitions"]), (
        f"la dimension {dimension} no aparece en definitions.md"
    )


@pytest.mark.parametrize("dimension", DIMENSIONES)
def test_toda_dimension_tiene_reparto_en_validators(
    documentos: dict[str, str], dimension: str
) -> None:
    assert _en_prosa(dimension) in _sin_tildes(documentos["validators"])


@pytest.mark.parametrize("rol", ROLES)
def test_todo_rol_que_el_codigo_nombra_esta_en_el_censo(
    documentos: dict[str, str], rol: str
) -> None:
    assert _en_prosa(rol) in _sin_tildes(documentos["architecture"])


@pytest.mark.parametrize("tarea", TIPOS_DE_TAREA)
def test_todo_tipo_de_tarea_esta_en_el_censo(documentos: dict[str, str], tarea: str) -> None:
    assert f"`{tarea}`" in documentos["architecture"]


# --- Lo que se retiro no queda narrado como historia -----------------------


def test_los_docs_describen_el_estado_actual(documentos: dict[str, str]) -> None:
    """Lo que se quita, se quita; no se cuenta en pasado."""
    for nombre in ("architecture", "agents"):
        texto = documentos[nombre]
        assert "no hay código todavía" not in texto.lower()
        assert "antes se llamaba" not in texto.lower()


def test_las_tres_decisiones_que_la_spec_cierra_ya_no_estan_abiertas(
    documentos: dict[str, str],
) -> None:
    abiertas = documentos["architecture"].split("## 8. Decisiones abiertas")[1]
    assert "Dónde vive el almacén de artefactos" not in abiertas
    assert "prompts de los once agentes son parte" not in abiertas
    assert "umbral de severidad dispara regeneración" not in abiertas
    # La de la herramienta externa de calculo sigue abierta, anotada.
    assert "herramienta externa de cálculo" in abiertas
    # La de la biblia la cerro el dueno del proyecto: se versiona con la novela.
    assert "versiona la biblia" not in abiertas


def test_el_ciclo_de_vida_no_promete_validadores_deterministas(
    documentos: dict[str, str],
) -> None:
    """La seccion 5 dice que no los hay: el diagrama no puede decir otra cosa."""
    assert "Redactado --> Validado: validadores deterministas" not in (
        documentos["architecture"]
    )
    assert "No hay validadores deterministas" in documentos["architecture"]


# --- El sistema dice lo mismo que los documentos --------------------------


def test_el_reparto_de_dimensiones_por_rol_coincide_con_validators(
    documentos: dict[str, str],
) -> None:
    """Diez en verificar, tres en editar_estilo, una en juzgar y siete en auditar."""
    del documentos
    reparto = {tarea: len(dimensiones_de(tarea)) for tarea in TIPOS_DE_TAREA}
    assert reparto["verificar"] == 10
    assert reparto["editar_estilo"] == 3
    assert reparto["juzgar"] == 1
    assert reparto["auditar"] == 7
    assert sum(reparto.values()) == len(DIMENSIONES)


def test_una_sola_dimension_no_admite_predicado(documentos: dict[str, str]) -> None:
    inverificables = [
        dimension
        for tarea in TIPOS_DE_TAREA
        for dimension in dimensiones_de(tarea)
        if contrato_de_verificacion(tarea, dimension)["metodo_de_verificacion"]
        == "inverificable"
    ]
    assert inverificables == ["coherencia_de_voz"]
    assert "coherencia de voz" in documentos["validators"].lower()


def _nombre_en_prosa(tipo: str) -> str:
    """De `RegistroLinguistico` a «registro linguistico», como se escribe."""
    partes: list[str] = []
    for letra in tipo:
        if letra.isupper() and partes:
            partes.append(" ")
        partes.append(letra)
    return _sin_tildes("".join(partes))


@pytest.mark.parametrize("tipo", TIPOS_DE_LA_CAPA_MUNDO)
def test_toda_entidad_de_la_capa_mundo_esta_definida(
    documentos: dict[str, str], tipo: str
) -> None:
    """Un tipo que el codigo guarda y la ontologia no nombra no existe: o se
    define, o sobra."""
    nombre = _nombre_en_prosa(tipo)
    for documento in ("definitions", "domain-knowledge"):
        assert nombre in _sin_tildes(documentos[documento]), (
            f"{tipo} no aparece en {documento}.md"
        )


@pytest.mark.parametrize("grado", LICENCIA)
def test_todo_grado_de_licencia_esta_en_los_dos_documentos(
    documentos: dict[str, str], grado: str
) -> None:
    """El grado de licencia es lo que separa un error de una decision, y desde
    que existe `personal`, tambien de un regalo. Los tres sitios donde esta
    escrito tienen que decir lo mismo."""
    for nombre in ("definitions", "domain-knowledge"):
        assert grado in _sin_tildes(documentos[nombre]), (
            f"el grado {grado} no aparece en {nombre}.md"
        )


def test_el_techo_es_el_mismo_en_los_tres_sitios_donde_esta_escrito(
    documentos: dict[str, str],
) -> None:
    from novela.ajustes import TECHO_DE_CONTEXTO_CONCURRENTE

    assert TECHO_DE_CONTEXTO_CONCURRENTE == 100_000
    for nombre in ("architecture", "agents"):
        assert "100 000" in documentos[nombre]
