"""Etapa 6: las doce carpetas de tarea.

Cierre por `prueba` y `analisis`: se enumeran las carpetas contra el censo y son
doce, una por rol; lo que cada una declara escribir coincide con la tabla de
gobierno; las veintiuna dimensiones tienen contrato y coinciden con el guion; un
artefacto roto a proposito produce `Critica` bloqueante con objeto el artefacto
y no llega al Revisor; y el pliegue incremental da lo mismo que plegar el log
entero.

La medida de deteccion y falsos positivos por dimension va marcada `gasta`: la
primera medida fija la linea base, no exige umbral.
"""

from pathlib import Path

import pytest

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.nucleo import guion
from novela.nucleo.caminante import Caminante
from novela.nucleo.gobierno import QUIEN_ESCRIBE, escrituras_de
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import MATERIALES
from novela.tareas import (
    CatalogoDelRepositorio,
    contrato_de_tarea,
    contrato_de_verificacion,
    dimensiones_de,
    esquema_de_tarea,
    prompt_de_tarea,
    tareas_declaradas,
)
from novela.vocabularios import DIMENSIONES, ROL_DE_TAREA, ROLES, TIPOS_DE_TAREA

BRIEF = {"titulo": "Prueba", "epoca": "Sevilla, 1587", "capitulos_objetivo": 1}


# --- Un rol, una tarea, una carpeta ----------------------------------------


def test_las_carpetas_de_tarea_son_doce_una_por_rol() -> None:
    assert sorted(tareas_declaradas()) == sorted(TIPOS_DE_TAREA)
    assert len(tareas_declaradas()) == len(ROLES) == 12


@pytest.mark.parametrize("tarea", sorted(TIPOS_DE_TAREA))
def test_cada_carpeta_lleva_todo_lo_suyo_dentro(tarea: str) -> None:
    contrato = contrato_de_tarea(tarea)
    assert contrato["tarea"] == tarea
    assert contrato["rol"] == ROL_DE_TAREA[tarea]
    assert prompt_de_tarea(tarea).strip()
    assert esquema_de_tarea(tarea).strip()
    assert contrato["rechaza"], "una tarea que no rechaza nada no impone forma a nada"


@pytest.mark.parametrize("tarea", sorted(TIPOS_DE_TAREA))
def test_lo_que_cada_tarea_escribe_es_lo_que_la_tabla_de_gobierno_le_asigna(
    tarea: str,
) -> None:
    rol = ROL_DE_TAREA[tarea]
    assert set(contrato_de_tarea(tarea)["escribe"]) == escrituras_de(rol)


@pytest.mark.parametrize("tarea", sorted(TIPOS_DE_TAREA))
def test_solo_el_documentalista_tiene_herramientas(tarea: str) -> None:
    herramientas = contrato_de_tarea(tarea)["herramientas"]
    if tarea == "documentar":
        assert herramientas == ["WebSearch", "WebFetch"]
    else:
        assert herramientas == []


def test_ningun_rol_escribe_un_tipo_que_no_exista() -> None:
    declarados = {
        tipo for tarea in TIPOS_DE_TAREA for tipo in contrato_de_tarea(tarea)["escribe"]
    }
    assert declarados <= set(QUIEN_ESCRIBE)


# --- Los veintiun contratos de verificacion --------------------------------


def test_las_veintiuna_dimensiones_tienen_contrato() -> None:
    con_contrato = {
        dimension for tarea in TIPOS_DE_TAREA for dimension in dimensiones_de(tarea)
    }
    assert con_contrato == set(DIMENSIONES)
    assert len(con_contrato) == 21


def test_el_reparto_por_tarea_es_diez_tres_una_y_siete() -> None:
    assert len(dimensiones_de("verificar")) == 10
    assert len(dimensiones_de("editar_estilo")) == 3
    assert len(dimensiones_de("juzgar")) == 1
    assert len(dimensiones_de("auditar")) == 7


@pytest.mark.parametrize(
    ("tarea", "dimension"),
    [(t, d) for t in sorted(TIPOS_DE_TAREA) for d in dimensiones_de(t)],
)
def test_cada_contrato_tiene_sus_tres_partes(tarea: str, dimension: str) -> None:
    """Predicado en una frase, proyeccion minima cerrada y forma de la `Critica`."""
    contrato = contrato_de_verificacion(tarea, dimension)
    assert contrato["predicado"].endswith(".")
    assert contrato["proyeccion_minima"]
    assert contrato["critica"]["severidad"]
    assert contrato["critica"]["evidencia_aceptada"]
    assert contrato["rol"] == ROL_DE_TAREA[tarea]


@pytest.mark.parametrize(
    ("tarea", "dimension"),
    [(t, d) for t in sorted(TIPOS_DE_TAREA) for d in dimensiones_de(t)],
)
def test_toda_proyeccion_minima_la_sabe_traer_el_ensamblador(
    tarea: str, dimension: str
) -> None:
    for material in contrato_de_verificacion(tarea, dimension)["proyeccion_minima"]:
        assert material in MATERIALES, f"{dimension} pide {material} y nadie sabe traerlo"


def test_el_guion_y_los_contratos_dicen_lo_mismo() -> None:
    """La criba y el rol de cada dimension estan escritos en dos sitios."""
    del_guion = {
        contrato.dimension: (nombre, contrato.rol)
        for nombre, contratos in guion.CRIBAS.items()
        for contrato in contratos
    }
    for tarea in TIPOS_DE_TAREA:
        for dimension in dimensiones_de(tarea):
            contrato = contrato_de_verificacion(tarea, dimension)
            assert del_guion[dimension] == (contrato["criba"], contrato["rol"])


def test_una_sola_dimension_sale_inverificable() -> None:
    inverificables = [
        dimension
        for tarea in TIPOS_DE_TAREA
        for dimension in dimensiones_de(tarea)
        if contrato_de_verificacion(tarea, dimension)["metodo_de_verificacion"]
        == "inverificable"
    ]
    assert inverificables == ["coherencia_de_voz"]
    contrato = contrato_de_verificacion("juzgar", "coherencia_de_voz")
    assert contrato["critica"]["ruidosa"] is True
    assert contrato["critica"]["rubrica"]


# --- El catalogo sirve lo que el guion pide --------------------------------


def test_el_catalogo_sirve_contrato_y_proyeccion_de_cada_dimension() -> None:
    catalogo = CatalogoDelRepositorio()
    contrato = catalogo.contrato("verificar", "integridad_de_pov")
    assert contrato is not None
    assert contrato["severidad"] == "bloqueante"
    assert catalogo.proyeccion_minima("verificar", "integridad_de_pov") == (
        "contrato_de_escena",
        "texto_producido",
    )
    assert catalogo.contrato("redactar", None) is None


# --- Un artefacto roto a proposito -----------------------------------------


def test_un_artefacto_roto_produce_critica_bloqueante_y_no_llega_al_revisor(
    tmp_path: Path,
) -> None:
    almacen: Almacen = abrir_almacen(tmp_path / "roto.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, EjecutorFingido())
    encargo = Encargo(
        paso=4,
        tarea="verificar",
        rol="verificador_de_continuidad",
        unidad="escena",
        proyeccion=(),
        id_obra=id_obra,
        capitulo=1,
        escena="esc_00000001",
    )
    roto = Artefacto(
        "Critica",
        {"evidencia": "algo"},
        id_obra=id_obra,
        capitulo=1,
        escena="esc_00000001",
        severidad="catastrofica",
    )

    from novela.nucleo.caminante import Resultado

    caminante._guardar(encargo, Resultado(artefactos=[roto]), "trz_00000001", 1)

    criticas = almacen.listar("Critica", id_obra)
    assert len(criticas) == 1
    unica = criticas[0]
    assert unica.severidad == "bloqueante"
    assert unica.cuerpo["objeto"] == "esc_00000001"
    assert "catastrofica" in unica.cuerpo["evidencia"]
    assert unica.cuerpo["detectada_por"]["rol"] is None
    almacen.cerrar()


# --- La propiedad del pliegue ----------------------------------------------


def test_replegar_desde_n_da_lo_mismo_que_plegar_el_log_entero(tmp_path: Path) -> None:
    """Estado en N-1 mas los eventos de N da lo mismo que plegar desde cero."""
    almacen: Almacen = abrir_almacen(tmp_path / "pliegue.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)
    for numero in (1, 2, 3):
        caminante.caminar_capitulo(id_obra, numero)

    de_una_pasada = [almacen.estado_en(id_obra, n) for n in (1, 2, 3)]
    assert de_una_pasada[2]["capitulos_plegados"] == [1, 2, 3]

    # Se regenera el capitulo 2: se descartan los estados de 2 en adelante y se
    # repliega hacia delante, capitulo a capitulo.
    caminante.replegar_desde(id_obra, 2, hasta=3)

    replegado = [almacen.estado_en(id_obra, n) for n in (1, 2, 3)]
    assert replegado == de_una_pasada
    almacen.cerrar()
