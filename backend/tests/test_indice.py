"""Etapa 4: el indice hibrido y la recuperacion.

Cierre por `prueba`: borrar el indice y reconstruirlo desde los artefactos
devuelve los mismos fragmentos; un borrador descartado no se recupera nunca
como eco; y ninguna consulta cruza de una obra a otra. Evidencia: la
comparacion de los dos indices y el intento de recuperar un descartado.
"""

from pathlib import Path

import pytest

from novela.ajustes import MODELO_DE_HUELLAS
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.indice import COLECCIONES, Indice, trocear

PROSA = (
    "Ines empujo la prensa hasta que el pliego salio limpio. En la calle de las "
    "Sierpes el alguacil Ordonez preguntaba por un impresor que nadie conocia. "
    "Olia a tinta y a miedo, y la noche del dos de abril de 1587 no prometia "
    "acabar tranquila para nadie del taller."
)

DESCARTADA = "Esta version murio en la primera criba y no debe volver jamas."


@pytest.fixture(scope="module")
def montado(tmp_path_factory: pytest.TempPathFactory) -> tuple[Almacen, Indice, str, str]:
    ruta = tmp_path_factory.mktemp("indice") / "indice.sqlite3"
    almacen = abrir_almacen(ruta)
    indice = Indice(almacen)
    primera = _sembrar(almacen, "La imprenta clandestina")
    segunda = _sembrar(almacen, "Otra obra que no debe mezclarse")
    for id_obra in (primera, segunda):
        indice.indexar_fuentes(id_obra, 1)
        indice.indexar_prosa_aceptada(id_obra, 1)
        indice.indexar_estructura(id_obra, 1)
    yield almacen, indice, primera, segunda
    almacen.cerrar()


def _sembrar(almacen: Almacen, titulo: str) -> str:
    id_obra = almacen.crear_obra({"titulo": titulo})
    almacen.guardar(
        [
            Artefacto(
                "Capitulo", {"numero": 1}, id_obra=id_obra, capitulo=1, estado="planificado"
            )
        ]
    )
    id_escena = almacen.guardar(
        [
            Artefacto(
                "Escena",
                {"pov": "per_0001", "marco": {"lugar": "Sevilla", "instante": "1587-04-02"}},
                id_obra=id_obra,
                capitulo=1,
                orden=1,
                estado="planificado",
            )
        ]
    )[0]
    aceptado = almacen.guardar_borrador(
        Artefacto(
            "Borrador", {"texto": PROSA}, id_obra=id_obra, capitulo=1, escena=id_escena,
            estado="redactado",
        )
    )
    almacen.aceptar_borrador(aceptado)
    descartado = almacen.guardar_borrador(
        Artefacto(
            "Borrador", {"texto": DESCARTADA}, id_obra=id_obra, capitulo=1, escena=id_escena,
            estado="redactado",
        )
    )
    almacen.descartar_borrador(descartado)
    almacen.guardar(
        [
            Artefacto(
                "Fuente",
                {
                    "cita": "Ordenanzas de la imprenta, 1558",
                    "tipo": "primaria",
                    "texto_integro": (
                        "Ninguna persona pueda imprimir libro alguno sin licencia del "
                        "Consejo, so pena de perdimiento de bienes y destierro."
                    ),
                    "ambito": "Castilla",
                },
                id_obra=id_obra,
                capitulo=1,
            ),
            Artefacto(
                "ResumenCapitulo",
                {"que_paso": "Imprimieron el pliego pese al alguacil"},
                id_obra=id_obra,
                capitulo=1,
            ),
        ]
    )
    return id_obra


# --- Las tres colecciones y ninguna mas ------------------------------------


def test_hay_tres_colecciones_y_ninguna_mas() -> None:
    assert COLECCIONES == ("documental", "obra_prosa", "obra_estructura")


def test_cada_coleccion_tiene_fragmentos(montado: tuple[Almacen, Indice, str, str]) -> None:
    almacen, _, id_obra, _ = montado
    for coleccion in COLECCIONES:
        fila = almacen._lector.execute(
            "SELECT COUNT(*) AS cuantos FROM fragmento WHERE id_obra = ? AND coleccion = ?",
            (id_obra, coleccion),
        ).fetchone()
        assert fila["cuantos"] > 0, coleccion


def test_el_troceado_solapa_lo_declarado() -> None:
    trozos = trocear("a" * 2000)
    assert len(trozos) > 1
    assert all(len(trozo) <= 900 for trozo in trozos)


# --- Solo se indexa texto aceptado -----------------------------------------


def test_un_borrador_descartado_no_se_recupera_nunca_como_eco(
    montado: tuple[Almacen, Indice, str, str],
) -> None:
    almacen, indice, id_obra, _ = montado
    fila = almacen._lector.execute(
        "SELECT COUNT(*) AS cuantos FROM fragmento WHERE id_obra = ? AND texto LIKE ?",
        (id_obra, "%murio en la primera criba%"),
    ).fetchone()
    assert fila["cuantos"] == 0

    recuperados = indice.recuperar(
        id_obra, "obra_prosa", "version que murio en la primera criba", "editor_de_estilo"
    )
    assert all("primera criba" not in f["texto"] for f in recuperados)


# --- Ninguna consulta cruza de una obra a otra -----------------------------


def test_ninguna_consulta_cruza_de_una_obra_a_otra(
    montado: tuple[Almacen, Indice, str, str],
) -> None:
    _, indice, primera, segunda = montado
    for id_obra in (primera, segunda):
        recuperados = indice.recuperar(
            id_obra, "obra_prosa", "el alguacil Ordonez", "editor_de_estilo"
        )
        assert recuperados
        artefactos = [f["artefacto"] for f in recuperados]
        del artefactos  # la particion la impone vec0; lo que se comprueba es el reparto
        fragmentos = {f["id"] for f in recuperados}
        otros = {
            f["id"]
            for f in indice.recuperar(
                segunda if id_obra == primera else primera,
                "obra_prosa",
                "el alguacil Ordonez",
                "editor_de_estilo",
            )
        }
        assert fragmentos.isdisjoint(otros)


# --- La busqueda es hibrida -------------------------------------------------


def test_la_palabra_exacta_encuentra_lo_que_el_parecido_no(
    montado: tuple[Almacen, Indice, str, str],
) -> None:
    """El nombre propio y la fecha exacta son justo lo que peor encuentra el
    parecido de sentido, y son la mitad de lo que el Documentalista busca."""
    _, indice, id_obra, _ = montado
    por_palabra = indice._por_palabra(id_obra, "obra_prosa", "Ordonez", 10)
    assert por_palabra, "FTS5 no encuentra el nombre propio"


def test_las_dos_vias_se_funden_en_un_solo_orden(
    montado: tuple[Almacen, Indice, str, str],
) -> None:
    from novela.almacen.indice import _fundir

    fundido = _fundir([5, 7, 9], [9, 5, 3])
    assert fundido[0] == 5
    assert set(fundido) == {3, 5, 7, 9}


# --- El modelo queda registrado --------------------------------------------


def test_un_solo_modelo_en_el_indice_de_una_obra(
    montado: tuple[Almacen, Indice, str, str],
) -> None:
    _, indice, id_obra, _ = montado
    assert indice.modelos_en_uso(id_obra) == {MODELO_DE_HUELLAS}


# --- El reparto por rol ------------------------------------------------------


@pytest.mark.parametrize(
    "rol",
    ["verificador_de_continuidad", "contable_de_estado", "arquitecto_de_arcos", "redactor"],
)
def test_los_roles_que_no_consultan_por_parecido_no_recuperan_nada(
    montado: tuple[Almacen, Indice, str, str], rol: str
) -> None:
    """Una busqueda por semejanza no encuentra lo que falta y su fallo es
    silencioso: estos cuatro quedan fuera por diseno."""
    _, indice, id_obra, _ = montado
    assert indice.recuperar(id_obra, "obra_prosa", "el alguacil", rol) == []


def test_lo_recuperado_no_pasa_de_la_k_declarada(
    montado: tuple[Almacen, Indice, str, str],
) -> None:
    _, indice, id_obra, _ = montado
    recuperados = indice.recuperar(
        id_obra, "documental", "licencia del Consejo", "documentalista"
    )
    assert 0 < len(recuperados) <= 8


# --- El indice es derivado ---------------------------------------------------


def test_borrarlo_y_reconstruirlo_devuelve_los_mismos_fragmentos(tmp_path: Path) -> None:
    """El indice es derivado; los artefactos no."""
    almacen = abrir_almacen(tmp_path / "reconstruido.sqlite3")
    indice = Indice(almacen)
    id_obra = _sembrar(almacen, "Obra que se reindexa")
    indice.indexar_fuentes(id_obra, 1)
    indice.indexar_prosa_aceptada(id_obra, 1)
    indice.indexar_estructura(id_obra, 1)

    antes = _huella_del_indice(almacen, id_obra)
    cuantos = indice.reconstruir(id_obra)
    despues = _huella_del_indice(almacen, id_obra)

    assert cuantos == len(antes)
    assert antes == despues
    almacen.cerrar()


def _huella_del_indice(almacen: Almacen, id_obra: str) -> list[tuple[str, str, str, int]]:
    return sorted(
        (fila["coleccion"], fila["artefacto"], fila["texto"], fila["orden"])
        for fila in almacen._lector.execute(
            "SELECT coleccion, artefacto, texto, orden FROM fragmento WHERE id_obra = ?",
            (id_obra,),
        )
    )
