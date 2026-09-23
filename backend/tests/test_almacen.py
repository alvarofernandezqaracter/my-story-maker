"""Etapa 1: el almacen.

Cierre por `prueba` y `analisis`. Lo que se comprueba aqui sale de la etapa 1
del plan: escritura y lectura de cada tipo de artefacto, un cambio sobre un
inmutable que falla, un valor fuera de vocabulario que se rechaza, un artefacto
caducado que deja de servirse, el descarte de los estados materializados de N
en adelante y la comprobacion de que ningun cuerpo de escena lleva dentro una
ficha de mundo.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from novela.almacen import Almacen, Artefacto, ArtefactoRechazado, EscrituraProhibida, esquema
from novela.almacen.artefactos import abrir_almacen, nombre_de_tabla
from novela.almacen.migraciones import MIGRACIONES

PATRON_DE_ID = re.compile(r"^[a-z]{3}_[0-9a-f]{8}$")

# Claves que solo aparecen en una ficha de mundo. Si alguna asoma dentro del
# cuerpo de una `Escena`, la capa Obra esta duplicando la capa Mundo en vez de
# referenciarla por `id`.
CLAVES_DE_FICHA_DE_MUNDO = {
    "rasgos_fisicos",
    "voz",
    "motivacion_dominante",
    "estatus_ontologico",
    "disponibilidad_temporal",
    "jerarquia",
    "extraccion_social",
}


@pytest.fixture
def almacen(tmp_path: Path) -> Almacen:
    tienda = abrir_almacen(tmp_path / "prueba.sqlite3")
    yield tienda
    tienda.cerrar()


@pytest.fixture
def id_obra(almacen: Almacen) -> str:
    return almacen.crear_obra(
        {
            "titulo": "El taller de la calle de las Sierpes",
            "epoca": "Sevilla, 1587",
            "premisa": "Una impresora clandestina",
            "tesis_tematica": "Lo que se imprime no se desimprime",
            "elenco_declarado": [],
            "politicas_globales": {"pov": "tercera_limitada"},
        }
    )


def _artefacto_de_prueba(tipo: str, id_obra: str) -> Artefacto:
    tabla = esquema.TABLA_POR_TIPO[tipo]
    artefacto = Artefacto(tipo=tipo, cuerpo={"nota": f"{tipo} de prueba"}, id_obra=id_obra)
    if "capitulo" in tabla.consulta:
        artefacto.capitulo = 1
    if "escena" in tabla.consulta:
        artefacto.escena = "esc_00000001"
    if "estado" in tabla.consulta and tabla.vocabulario_de_estado:
        artefacto.estado = tabla.vocabulario_de_estado[0]
    if "severidad" in tabla.consulta:
        artefacto.severidad = "mayor"
    if "dimension" in tabla.consulta:
        artefacto.dimension = "continuidad_de_estado"
    if "rol" in tabla.consulta:
        artefacto.rol = "verificador_de_continuidad"
    for propia in tabla.propias:
        if propia.nombre in {"orden", "version", "intento"}:
            setattr(artefacto, propia.nombre, 1)
    return artefacto


# --- Escritura y lectura de cada tipo --------------------------------------


@pytest.mark.parametrize("tipo", [t.tipo for t in esquema.TABLAS if t.tipo != "Obra"])
def test_cada_tipo_de_artefacto_se_escribe_y_se_lee(
    almacen: Almacen, id_obra: str, tipo: str
) -> None:
    identificador = almacen.guardar([_artefacto_de_prueba(tipo, id_obra)])[0]
    leido = almacen.leer(tipo, identificador)
    assert leido is not None
    assert leido.tipo == tipo
    assert leido.cuerpo == {"nota": f"{tipo} de prueba"}
    assert PATRON_DE_ID.match(identificador), identificador


def test_la_obra_se_crea_y_cuelga_de_si_misma(almacen: Almacen, id_obra: str) -> None:
    obra = almacen.leer_obra(id_obra)
    assert obra is not None
    assert obra.id_obra == obra.id
    assert almacen.esta_detenida(id_obra) is False


# --- Lo inmutable no se toca y nada se borra -------------------------------


@pytest.mark.parametrize("tipo", esquema.TIPOS_INMUTABLES)
def test_un_cambio_sobre_un_inmutable_falla(almacen: Almacen, id_obra: str, tipo: str) -> None:
    identificador = almacen.guardar([_artefacto_de_prueba(tipo, id_obra)])[0]
    with pytest.raises(EscrituraProhibida):
        almacen._actualizar(tipo, identificador, {"cuerpo": json.dumps({"nota": "otra"})})


def test_un_borrador_aceptado_es_inmutable(almacen: Almacen, id_obra: str) -> None:
    borrador = _artefacto_de_prueba("Borrador", id_obra)
    borrador.estado = "redactado"
    identificador = almacen.guardar_borrador(borrador)
    almacen.aceptar_borrador(identificador)
    with pytest.raises(EscrituraProhibida):
        almacen.descartar_borrador(identificador)


@pytest.mark.parametrize("tipo", [t.tipo for t in esquema.TABLAS if t.tipo != "Obra"])
def test_ningun_artefacto_se_borra(almacen: Almacen, id_obra: str, tipo: str) -> None:
    almacen.guardar([_artefacto_de_prueba(tipo, id_obra)])
    with pytest.raises(sqlite3.IntegrityError, match="no se borra nada"):
        almacen._escritor.execute(f"DELETE FROM {nombre_de_tabla(tipo)}")


# --- Vocabularios controlados ----------------------------------------------


@pytest.mark.parametrize(
    ("columna", "valor"),
    [
        ("severidad", "catastrofica"),
        ("dimension", "que_bonito_queda"),
        ("rol", "jefe_de_planta"),
        ("estado", "pendiente_de_mirar"),
    ],
)
def test_un_valor_fuera_de_vocabulario_se_rechaza(
    almacen: Almacen, id_obra: str, columna: str, valor: str
) -> None:
    critica = _artefacto_de_prueba("Critica", id_obra)
    setattr(critica, columna, valor)
    with pytest.raises(ArtefactoRechazado):
        almacen.guardar([critica])


def test_un_tipo_que_no_existe_se_rechaza(almacen: Almacen, id_obra: str) -> None:
    with pytest.raises(ArtefactoRechazado):
        almacen.guardar([Artefacto(tipo="Cronometro", cuerpo={}, id_obra=id_obra)])


def test_la_unidad_se_escribe_entera_o_nada(almacen: Almacen, id_obra: str) -> None:
    buena = _artefacto_de_prueba("Critica", id_obra)
    mala = _artefacto_de_prueba("Critica", id_obra)
    mala.severidad = "gravisima"
    with pytest.raises(ArtefactoRechazado):
        almacen.guardar([buena, mala])
    assert almacen.listar("Critica", id_obra) == []


# --- Caducidad de la memoria de capitulo -----------------------------------


def test_un_artefacto_caducado_deja_de_servirse(almacen: Almacen, id_obra: str) -> None:
    critica = _artefacto_de_prueba("Critica", id_obra)
    identificador = almacen.guardar_critica(critica)
    assert len(almacen.listar_criticas_abiertas(id_obra)) == 1

    caducados = almacen.caducar_memoria_de_capitulo(id_obra, 1)

    assert caducados >= 1
    assert almacen.listar("Critica", id_obra) == []
    assert almacen.leer("Critica", identificador) is None
    assert almacen.leer("Critica", identificador, incluir_caducados=True) is not None


def test_lo_que_es_memoria_de_obra_no_caduca_con_el_capitulo(
    almacen: Almacen, id_obra: str
) -> None:
    resumen = _artefacto_de_prueba("ResumenCapitulo", id_obra)
    almacen.guardar([resumen])
    almacen.caducar_memoria_de_capitulo(id_obra, 1)
    assert len(almacen.listar("ResumenCapitulo", id_obra, capitulo=1)) == 1


# --- El estado materializado es cache descartable --------------------------


def test_descartar_los_estados_desde_n_y_volver_a_plegar_da_lo_mismo(
    almacen: Almacen, id_obra: str
) -> None:
    plegado = {n: {"capitulo": n, "ubicacion": f"lugar_{n}"} for n in (1, 2, 3)}
    for numero, cuerpo in plegado.items():
        almacen.materializar_estado(id_obra, numero, cuerpo)

    descartados = almacen.descartar_estados_desde(id_obra, 2)

    assert descartados == 2
    assert almacen.estado_en(id_obra, 1) == plegado[1]
    assert almacen.estado_en(id_obra, 2) is None
    for numero in (2, 3):
        almacen.materializar_estado(id_obra, numero, plegado[numero])
    assert [almacen.estado_en(id_obra, n) for n in (1, 2, 3)] == list(plegado.values())


# --- Las tres capas no se mezclan ------------------------------------------


def test_ninguna_clave_foranea_apunta_a_la_capa_de_produccion(almacen: Almacen) -> None:
    """La capa Produccion observa a las otras dos; ninguna la observa a ella."""
    tablas_de_produccion = {
        nombre_de_tabla(t.tipo) for t in esquema.TABLAS if t.capa == "produccion"
    }
    infractoras: list[tuple[str, str]] = []
    for tabla in esquema.TABLAS:
        if tabla.capa == "produccion":
            continue
        nombre = nombre_de_tabla(tabla.tipo)
        for fila in almacen._lector.execute(f"PRAGMA foreign_key_list({nombre})"):
            if fila["table"] in tablas_de_produccion:
                infractoras.append((nombre, fila["table"]))
    assert infractoras == []


def test_ningun_cuerpo_de_escena_contiene_una_ficha_de_mundo(
    almacen: Almacen, id_obra: str
) -> None:
    """La capa Obra referencia la capa Mundo por `id` y nunca la duplica.

    Evidencia citable: el recuento de referencias al mundo que no son `id`.
    """
    personaje = Artefacto(
        tipo="Personaje",
        id_obra=id_obra,
        cuerpo={"nombre": "Ines de Salcedo", "voz": {"muletillas": ["a fe mia"]}},
    )
    id_personaje = almacen.guardar([personaje])[0]
    escena = Artefacto(
        tipo="Escena",
        id_obra=id_obra,
        capitulo=1,
        orden=1,
        estado="planificado",
        cuerpo={
            "pov": id_personaje,
            "elenco_presente": [id_personaje],
            "marco": {"lugar": "lug_00000001", "instante": "1587-04-02"},
        },
    )
    almacen.guardar([escena])

    referencias_que_no_son_id = _referencias_que_no_son_id(almacen, id_obra)

    assert referencias_que_no_son_id == []


def _referencias_que_no_son_id(almacen: Almacen, id_obra: str) -> list[str]:
    hallazgos: list[str] = []

    def recorrer(nodo: Any, camino: str) -> None:
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                if clave in CLAVES_DE_FICHA_DE_MUNDO:
                    hallazgos.append(f"{camino}.{clave}")
                recorrer(valor, f"{camino}.{clave}")
        elif isinstance(nodo, list):
            for indice, valor in enumerate(nodo):
                recorrer(valor, f"{camino}[{indice}]")

    for escena in almacen.listar("Escena", id_obra):
        recorrer(escena.cuerpo, escena.id)
    return hallazgos


# --- Migraciones ------------------------------------------------------------


def test_las_migraciones_son_idempotentes(tmp_path: Path) -> None:
    ruta = tmp_path / "migrada.sqlite3"
    primera = abrir_almacen(ruta)
    assert primera.migrar() == len(MIGRACIONES)
    primera.cerrar()
    segunda = abrir_almacen(ruta)
    assert segunda.migrar() == len(MIGRACIONES)
    segunda.cerrar()


def test_una_tanda_de_escrituras_concurrentes_no_se_pisa(
    almacen: Almacen, id_obra: str
) -> None:
    """El bloqueo por escrituras concurrentes se ejercita, no se supone.

    Diez tareas de una tanda escribiendo a la vez es el caso real: el turno de
    escritura las serializa y ninguna se pierde ni revienta por bloqueo.
    """
    from concurrent.futures import ThreadPoolExecutor

    def escribir(numero: int) -> str:
        critica = _artefacto_de_prueba("Critica", id_obra)
        critica.cuerpo = {"evidencia": f"linea {numero}"}
        return almacen.guardar_critica(critica)

    with ThreadPoolExecutor(max_workers=10) as tanda:
        identificadores = list(tanda.map(escribir, range(10)))

    assert len(set(identificadores)) == 10
    assert len(almacen.listar("Critica", id_obra)) == 10
