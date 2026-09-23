"""Etapa 2: el nucleo.

Cierre por `prueba` y `analisis`. El guion son diez pasos declarados, asi que
se enumera entero en lugar de razonar sobre el, y lo mismo con las cuatro
severidades, los dos topes de vueltas y las transiciones del ciclo de vida del
capitulo. Evidencia: esta suite y la tabla de anchura de tanda calculada rol
por rol contra los topes de `architecture.md` 3.
"""

import pytest

from novela.ajustes import (
    TOPE_DE_REGENERACIONES_POR_ESCENA,
    TOPE_DE_REVISIONES_POR_BORRADOR,
    TOPE_DE_VENTANA_POR_ROL,
    tokens_repartibles,
)
from novela.almacen import Artefacto
from novela.nucleo import calidad, ciclo, guion, presupuesto
from novela.nucleo.gobierno import (
    EscrituraNoAutorizada,
    comprobar_escritura,
    escrituras_de,
    puede_escribir,
)
from novela.vocabularios import DIMENSIONES, ROLES, SEVERIDAD, TAREA_DE_ROL

# El guion tal como esta escrito en `architecture.md` 4. Si el TOML y esta
# tabla dejan de coincidir, uno de los dos esta mal.
GUION_DECLARADO = [
    (1, "planificar", "planificador", "solo"),
    (2, "documentar", "documentalista", "por_escena"),
    (3, "redactar", "redactor", "por_escena"),
    (4, "verificar", None, "por_dimension_y_escena"),
    (5, "revisar", "revisor", "por_escena"),
    (6, "verificar", None, "por_dimension_y_escena"),
    (7, "editar_estilo", "editor_de_estilo", "solo"),
    (8, "criba", None, "por_dimension_y_escena"),
    (9, "plegar", "contable_de_estado", "solo"),
    (10, "destilar", "archivero", "solo"),
]


# --- El guion se enumera entero --------------------------------------------


def test_el_guion_son_diez_pasos_en_ese_orden() -> None:
    enumerado = [(p.numero, p.tarea, p.rol, p.concurrencia) for p in guion.PASOS]
    assert enumerado == GUION_DECLARADO


def test_las_dos_tareas_sin_cadencia_de_capitulo_van_fuera_y_solas() -> None:
    assert set(guion.FUERA_DEL_GUION) == {"poblar_mundo", "auditar"}
    for paso in guion.FUERA_DEL_GUION.values():
        assert paso.concurrencia == "solo"


def test_las_cribas_reparten_las_veintiuna_dimensiones_y_ninguna_se_repite() -> None:
    repartidas = [c.dimension for contratos in guion.CRIBAS.values() for c in contratos]
    assert sorted(repartidas) == sorted(DIMENSIONES)
    assert len(set(repartidas)) == len(repartidas)
    assert len(repartidas) == 21


def test_el_reparto_por_criba_es_el_de_validators() -> None:
    cuantas = {nombre: len(contratos) for nombre, contratos in guion.CRIBAS.items()}
    assert cuantas == {"bloqueantes": 5, "mayores": 4, "pulido": 5, "global": 7}


def test_cada_contrato_lo_comprueba_un_rol_del_censo_con_su_propia_tarea() -> None:
    for contratos in guion.CRIBAS.values():
        for contrato in contratos:
            assert contrato.rol in ROLES
            assert TAREA_DE_ROL[contrato.rol] in {
                "verificar",
                "editar_estilo",
                "juzgar",
                "auditar",
            }


def test_una_dimension_por_invocacion() -> None:
    encargos = guion.expandir(
        guion.paso(4), id_obra="obr_1", capitulo=1, escenas=("esc_1", "esc_2")
    )
    assert len(encargos) == 10
    assert all(encargo.dimension is not None for encargo in encargos)
    assert len({(e.escena, e.dimension) for e in encargos}) == 10


# --- El presupuesto ---------------------------------------------------------


def test_la_anchura_de_tanda_se_calcula_rol_por_rol() -> None:
    """La tabla de anchura de tanda: `80 000 / lo que cuesta abrir el rol`.

    Lo que cuesta abrir no es solo la proyeccion: un subagente de Claude Code
    arrastra su propio sistema y sus definiciones de herramienta, medidos en
    10 256 tokens, y eso ocupa techo como cualquier otra entrada.
    """
    tabla = {
        rol: tokens_repartibles() // presupuesto.coste_de_abrir(tope)
        for rol, tope in TOPE_DE_VENTANA_POR_ROL.items()
    }
    assert tabla["verificador_de_continuidad"] == 4
    assert tabla["juez_de_rubrica"] == 4
    assert tabla["arquitecto_de_arcos"] == 2
    assert tabla["planificador"] == 2
    assert tabla["redactor"] == 3
    for rol, anchura in tabla.items():
        encargo = guion.Encargo(1, TAREA_DE_ROL[rol], rol, "escena", ())
        assert presupuesto.anchura_de_tanda([encargo]) == anchura


def test_veinte_comprobaciones_de_verificador_son_cinco_tandas_de_cuatro() -> None:
    encargos = guion.expandir(
        guion.paso(4), id_obra="obr_1", capitulo=1, escenas=tuple(f"esc_{n}" for n in range(4))
    )
    tandas = presupuesto.repartir_en_tandas(encargos)
    assert [len(tanda) for tanda in tandas] == [4, 4, 4, 4, 4]


def test_la_tanda_la_marca_el_rol_mas_caro() -> None:
    caro = guion.Encargo(8, "juzgar", "juez_de_rubrica", "escena", ())
    barato = guion.Encargo(8, "editar_estilo", "editor_de_estilo", "escena", ())
    assert presupuesto.anchura_de_tanda([caro, barato]) == 4


def test_si_no_cabe_se_parte_la_unidad_y_nunca_se_recorta_la_proyeccion() -> None:
    assert presupuesto.partir_unidad("capitulo") == "escena"
    assert presupuesto.partir_unidad("escena") == "parrafo"
    with pytest.raises(presupuesto.NoCabeNiPartiendo):
        presupuesto.partir_unidad("parrafo")


def test_lo_recuperado_paga_en_el_tope_del_rol_y_si_no_cabe_baja_k() -> None:
    assert presupuesto.k_que_cabe("documentalista", 0, 8_000, 300) == 8
    assert presupuesto.k_que_cabe("documentalista", 7_100, 8_000, 300) == 3
    assert presupuesto.k_que_cabe("documentalista", 8_000, 8_000, 300) == 0
    assert presupuesto.k_que_cabe("verificador_de_continuidad", 0, 8_000, 300) == 0


def test_el_techo_cuenta_solo_la_entrada_pero_toda_la_entrada() -> None:
    assert presupuesto.pico_admisible(80_000, 9_500) is True
    assert presupuesto.pico_admisible(80_000, 9_501) is False


# --- El enrutado por severidad y los topes de vueltas ----------------------


def test_las_cuatro_severidades_tienen_destino_y_no_hay_una_quinta() -> None:
    assert set(calidad.DESTINO_POR_SEVERIDAD) == set(SEVERIDAD)
    assert calidad.DESTINO_POR_SEVERIDAD["bloqueante"] == "regenerar_escena"
    assert calidad.DESTINO_POR_SEVERIDAD["mayor"] == "revision_dirigida"
    assert calidad.DESTINO_POR_SEVERIDAD["menor"] == "criba_de_pulido"
    assert calidad.DESTINO_POR_SEVERIDAD["sugerencia"] == "criba_de_pulido"


def _critica(severidad: str, evidencia: str = "«llovia» dos veces") -> Artefacto:
    return Artefacto(
        tipo="Critica", cuerpo={"evidencia": evidencia}, severidad=severidad, escena="esc_1"
    )


def test_una_critica_sin_evidencia_se_descarta_antes_de_llegar_al_revisor() -> None:
    enrutado = calidad.enrutar(
        [_critica("bloqueante", ""), _critica("mayor", "   "), _critica("menor")]
    )
    assert len(enrutado.descartadas_sin_evidencia) == 2
    assert enrutado.regenerar_escena == []
    assert len(enrutado.criba_de_pulido) == 1


def test_el_enrutado_reparte_por_lo_que_puede_parar() -> None:
    enrutado = calidad.enrutar(
        [_critica("bloqueante"), _critica("mayor"), _critica("menor"), _critica("sugerencia")]
    )
    assert len(enrutado.regenerar_escena) == 1
    assert len(enrutado.revision_dirigida) == 1
    assert len(enrutado.criba_de_pulido) == 2
    assert enrutado.hay_bloqueantes and enrutado.hay_mayores


def test_los_dos_topes_de_vueltas() -> None:
    assert TOPE_DE_REVISIONES_POR_BORRADOR == 2
    assert TOPE_DE_REGENERACIONES_POR_ESCENA == 2
    assert calidad.queda_regeneracion(1) is True
    assert calidad.queda_regeneracion(2) is False
    assert calidad.queda_revision(1) is True
    assert calidad.queda_revision(2) is False
    assert calidad.se_acepta_con_criticas_abiertas(2, 2) is True


def test_la_doble_pasada_en_desacuerdo() -> None:
    constancias = [
        {"objeto": "esc_1", "dimension": "integridad_de_pov", "cumple": True},
        {"objeto": "esc_1", "dimension": "integridad_de_pov", "cumple": False},
    ]
    assert calidad.hay_desacuerdo(constancias) is True
    assert calidad.hay_desacuerdo(constancias[:1]) is False
    rebajada = calidad.rebajar_a_sugerencia(_critica("bloqueante"))
    assert rebajada.severidad == "sugerencia"
    assert rebajada.cuerpo["caso_ambiguo"] is True


# --- El ciclo de vida del capitulo -----------------------------------------


def test_las_transiciones_del_ciclo_de_vida_se_enumeran() -> None:
    assert {
        "planificado": frozenset({"redactado", "descartado"}),
        "redactado": frozenset({"validado"}),
        "validado": frozenset({"redactado", "en_revision", "aceptado"}),
        "en_revision": frozenset({"validado"}),
        "aceptado": frozenset({"cerrado"}),
        "cerrado": frozenset(),
        "descartado": frozenset(),
    } == ciclo.TRANSICIONES


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [("planificado", "aceptado"), ("cerrado", "redactado"), ("redactado", "cerrado")],
)
def test_un_salto_que_el_ciclo_no_contempla_falla(desde: str, hasta: str) -> None:
    with pytest.raises(ciclo.TransicionImposible):
        ciclo.transitar(desde, hasta)


def test_a_donde_va_un_capitulo_tras_la_criba() -> None:
    assert ciclo.siguiente_tras_criba(True, True) == "redactado"
    assert ciclo.siguiente_tras_criba(False, True) == "en_revision"
    assert ciclo.siguiente_tras_criba(False, False) == "aceptado"


# --- Los permisos por rol ---------------------------------------------------


def test_ningun_agente_valida_su_propia_salida() -> None:
    assert not puede_escribir("redactor", "Critica")
    assert not puede_escribir("verificador_de_continuidad", "Borrador")
    assert not puede_escribir("juez_de_rubrica", "Borrador")
    assert not puede_escribir("revisor", "Critica")


def test_el_mundo_solo_cambia_por_evento_de_estado_del_contable() -> None:
    for rol in ROLES:
        if rol != "contable_de_estado":
            assert not puede_escribir(rol, "EventoEstado")
    assert puede_escribir("contable_de_estado", "EventoEstado")


def test_solo_el_documentalista_escribe_fuente() -> None:
    for rol in ROLES:
        assert puede_escribir(rol, "Fuente") is (rol == "documentalista")


@pytest.mark.parametrize("rol", ROLES)
def test_cada_rol_tiene_enumerado_lo_que_puede_escribir(rol: str) -> None:
    """Todo rol de la obra puede dejar una `Decision`. El Entrevistador actua
    antes de que la obra exista y no escribe nada (SPEC1 RF-70)."""
    escrituras = escrituras_de(rol)
    if rol == "entrevistador":
        assert escrituras == frozenset()
        return
    assert "Decision" in escrituras
    assert "Obra" not in escrituras
    assert "Traza" not in escrituras


def test_la_escritura_prohibida_falla_con_el_nombre_del_rol_y_la_entidad() -> None:
    with pytest.raises(EscrituraNoAutorizada, match="redactor"):
        comprobar_escritura("redactor", "EventoEstado")
