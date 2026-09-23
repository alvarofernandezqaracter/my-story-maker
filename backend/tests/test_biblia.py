"""El uso de los hechos por capitulo y la cronologia (SPEC1 §4.9).

Cierre por `prueba`, `inspeccion` y `demostracion` de RF-80 a RF-88. Lo que se
comprueba: que la `Mencion` es un artefacto inmutable de la capa Obra que solo
escribe el Archivero y que la ficha del hecho no se toca; que una mencion sin
hecho o a un hecho que no es de esa obra se rechaza; que los capitulos de uso y
la cronologia se derivan y no se guardan; que la ventana del Archivero lleva el
indice de la biblia y no el canon; y que las dos rutas de lectura sirven lo
mismo que el almacen. Evidencia: esta suite y el contrato de frontera publicado.
"""

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen, Artefacto, ArtefactoRechazado, EscrituraProhibida
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.esquema import TABLA_POR_TIPO
from novela.api.aplicacion import crear_aplicacion, operaciones_de_escritura
from novela.nucleo import guion
from novela.nucleo.caminante import Caminante
from novela.nucleo.gobierno import QUIEN_ESCRIBE
from novela.nucleo.proyecciones import MATERIALES, Peticion
from novela.tareas import contrato_de_tarea, esquema_de_tarea, prompt_de_tarea
from novela.vocabularios import HECHOS_DE_LA_BIBLIA, LICENCIA

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "capitulos_objetivo": 2,
    "politicas_globales": {"pov": "tercera_limitada"},
    "arcos": ["Ines pasa del miedo al desafio"],
}


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    tienda = abrir_almacen(tmp_path / "biblia.sqlite3")
    yield tienda
    tienda.cerrar()


@pytest.fixture
def id_obra(almacen: Almacen) -> str:
    return almacen.crear_obra(BRIEF)


def _ficha(almacen: Almacen, id_obra: str, tipo: str, cuerpo: dict) -> str:
    return almacen.guardar([Artefacto(tipo=tipo, cuerpo=cuerpo, id_obra=id_obra)])[0]


def _mencion(id_obra: str, hecho: str | None, capitulo: int | None = 1) -> Artefacto:
    cuerpo = {"hecho": hecho} if hecho is not None else {}
    return Artefacto(tipo="Mencion", cuerpo=cuerpo, id_obra=id_obra, capitulo=capitulo)


# --- RF-80. La mencion es un artefacto de la capa Obra, y la ficha no cambia -


def test_la_mencion_es_de_la_capa_obra_inmutable_y_de_memoria_de_obra() -> None:
    tabla = TABLA_POR_TIPO["Mencion"]
    assert tabla.capa == "obra"
    assert tabla.memoria == "obra"
    assert tabla.inmutable


def test_anotar_un_uso_no_toca_la_ficha(almacen: Almacen, id_obra: str) -> None:
    ines = _ficha(almacen, id_obra, "Personaje", {"nombre": "Ines", "licencia": "plausible"})
    antes = almacen.leer("Personaje", ines)
    almacen.guardar([_mencion(id_obra, ines, 1), _mencion(id_obra, ines, 2)])

    despues = almacen.leer("Personaje", ines)
    assert despues is not None and antes is not None
    assert despues.cuerpo == antes.cuerpo


def test_una_mencion_no_se_modifica(almacen: Almacen, id_obra: str) -> None:
    ines = _ficha(almacen, id_obra, "Personaje", {"nombre": "Ines"})
    mencion = almacen.guardar([_mencion(id_obra, ines)])[0]
    with pytest.raises(EscrituraProhibida):
        almacen._actualizar("Mencion", mencion, {"capitulo": 7})


# --- RF-81. Solo el Archivero las escribe, al destilar ---------------------


def test_solo_el_archivero_escribe_menciones() -> None:
    assert QUIEN_ESCRIBE["Mencion"] == frozenset({"archivero"})
    assert "Mencion" in contrato_de_tarea("destilar")["escribe"]


def test_la_mencion_va_en_la_misma_unidad_que_el_resumen(
    almacen: Almacen, id_obra: str
) -> None:
    """O se guardan las dos cosas o ninguna: una mencion mala tumba el resumen."""
    resumen = Artefacto("ResumenCapitulo", {"que_paso": "algo"}, id_obra=id_obra, capitulo=1)
    with pytest.raises(ArtefactoRechazado):
        almacen.guardar([resumen, _mencion(id_obra, "per_00000000")])
    assert almacen.listar("ResumenCapitulo", id_obra) == []


# --- RF-82. El Archivero ve el indice de la biblia, no el canon ------------


def test_el_paso_de_destilar_lleva_el_indice_de_la_biblia_y_no_el_canon() -> None:
    paso = guion.paso(10)
    assert paso.tarea == "destilar"
    assert "indice_de_la_biblia" in paso.proyeccion
    assert "canon" not in paso.proyeccion
    assert "indice_de_la_biblia" in contrato_de_tarea("destilar")["entrada"]


def test_el_indice_trae_cuatro_campos_por_hecho_y_nada_mas(
    almacen: Almacen, id_obra: str
) -> None:
    _ficha(
        almacen,
        id_obra,
        "Personaje",
        {"nombre": "Nala", "licencia": "personal", "voz": {"muletillas": ["guau"]}},
    )
    _ficha(almacen, id_obra, "Evento", {"descripcion": "Auto de fe", "licencia": "canon"})
    _ficha(almacen, id_obra, "Fuente", {"cita": "Ordenanzas, 1558"})
    encargo = replace(guion.expandir(guion.paso(10), id_obra=id_obra, capitulo=1)[0])

    indice = MATERIALES["indice_de_la_biblia"](Peticion(almacen=almacen, encargo=encargo))

    assert {fila["nombre"] for fila in indice} == {"Nala", "Auto de fe"}
    assert all(set(fila) == {"id", "tipo", "nombre", "licencia"} for fila in indice)
    assert {fila["tipo"] for fila in indice} <= set(HECHOS_DE_LA_BIBLIA)


def test_el_prompt_y_el_esquema_del_archivero_piden_las_menciones() -> None:
    assert "Mencion" in prompt_de_tarea("destilar")
    tipos = {ejemplo["tipo"] for ejemplo in json.loads(esquema_de_tarea("destilar"))}
    assert tipos == {"ResumenCapitulo", "Mencion"}


# --- RF-83. Una mencion huerfana se rechaza --------------------------------


def test_una_mencion_sin_hecho_se_rechaza(almacen: Almacen, id_obra: str) -> None:
    with pytest.raises(ArtefactoRechazado, match="falta el id del hecho"):
        almacen.guardar([_mencion(id_obra, None)])


def test_una_mencion_sin_capitulo_se_rechaza(almacen: Almacen, id_obra: str) -> None:
    ines = _ficha(almacen, id_obra, "Personaje", {"nombre": "Ines"})
    with pytest.raises(ArtefactoRechazado, match="falta el capitulo"):
        almacen.guardar([_mencion(id_obra, ines, None)])


@pytest.mark.parametrize("hecho", ["per_00000000", "fue_00000000", "esc_00000000", "nada"])
def test_una_mencion_a_algo_que_no_es_un_hecho_de_la_obra_se_rechaza(
    almacen: Almacen, id_obra: str, hecho: str
) -> None:
    with pytest.raises(ArtefactoRechazado, match="no es un hecho de la biblia"):
        almacen.guardar([_mencion(id_obra, hecho)])


def test_una_mencion_a_un_hecho_de_otra_obra_se_rechaza(almacen: Almacen, id_obra: str) -> None:
    otra = almacen.crear_obra(BRIEF)
    ajena = _ficha(almacen, otra, "Personaje", {"nombre": "Ines"})
    with pytest.raises(ArtefactoRechazado, match="no es un hecho de la biblia"):
        almacen.guardar([_mencion(id_obra, ajena)])


def test_el_rechazo_de_una_mencion_sale_como_critica_bloqueante(tmp_path: Path) -> None:
    """RF-23: el rechazo es una `Critica` con objeto el artefacto."""
    almacen = abrir_almacen(tmp_path / "rechazo.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)

    class ArchiveroQueInventa(EjecutorFingido):
        def _destilar(self, encargo):  # type: ignore[no-untyped-def]
            resultado = super()._destilar(encargo)
            resultado.artefactos.append(
                Artefacto("Mencion", {"hecho": "per_inventado"}, capitulo=encargo.capitulo)
            )
            return resultado

    caminante = Caminante(almacen, ArchiveroQueInventa(), catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)
    caminante.caminar_capitulo(id_obra, 1)

    criticas = [
        c
        for c in almacen.listar("Critica", id_obra)
        if c.cuerpo.get("detectada_por", {}).get("tarea") == "destilar"
    ]
    assert len(criticas) == 1
    assert criticas[0].severidad == "bloqueante"
    assert "per_inventado" in criticas[0].cuerpo["evidencia"]
    almacen.cerrar()


# --- RF-84. Los capitulos de uso se derivan --------------------------------


def test_los_capitulos_de_uso_se_derivan_sin_repetir_y_en_orden(
    almacen: Almacen, id_obra: str
) -> None:
    ines = _ficha(almacen, id_obra, "Personaje", {"nombre": "Ines", "licencia": "plausible"})
    sevilla = _ficha(almacen, id_obra, "Lugar", {"nombre": "Sevilla", "licencia": "canon"})
    almacen.guardar(
        [
            _mencion(id_obra, ines, 3),
            _mencion(id_obra, ines, 1),
            _mencion(id_obra, ines, 3),
            _mencion(id_obra, sevilla, 2),
        ]
    )

    assert almacen.capitulos_de_uso(id_obra) == {ines: [1, 3], sevilla: [2]}


def test_un_hecho_sin_mencion_sale_con_la_lista_vacia(almacen: Almacen, id_obra: str) -> None:
    nala = _ficha(almacen, id_obra, "Personaje", {"nombre": "Nala", "licencia": "personal"})
    hechos = almacen.hechos_de_la_biblia(id_obra, licencia="personal")
    assert hechos == [
        {
            "id": nala,
            "tipo": "Personaje",
            "nombre": "Nala",
            "licencia": "personal",
            "capitulos": [],
        }
    ]


def test_la_consulta_de_uso_va_por_indice(almacen: Almacen, id_obra: str) -> None:
    plan = almacen._lector.execute(
        "EXPLAIN QUERY PLAN SELECT DISTINCT hecho, capitulo FROM artefacto_mencion "
        "WHERE id_obra = ? AND caducado_en IS NULL ORDER BY hecho, capitulo",
        (id_obra,),
    ).fetchall()
    detalle = " ".join(fila["detail"] for fila in plan)
    assert "USING INDEX" in detalle, detalle


# --- RF-85. Presentes y fechas ISO parciales, pedidos a quien los escribe --


def test_el_contable_escribe_los_presentes_y_la_fecha_iso() -> None:
    ejemplo = json.loads(esquema_de_tarea("plegar"))
    assert "presentes" in ejemplo["cuerpo"]
    prompt = prompt_de_tarea("plegar")
    assert "presentes" in prompt
    assert "AAAA-MM-DD" in prompt


@pytest.mark.parametrize("tarea", ["poblar_mundo", "planificar", "documentar"])
def test_quien_escribe_una_fecha_de_la_cronologia_la_pide_en_iso(tarea: str) -> None:
    assert "AAAA-MM-DD" in prompt_de_tarea(tarea)


# --- RF-86. La cronologia es una vista ordenada ----------------------------


def test_la_cronologia_no_tiene_tabla_propia() -> None:
    assert "Cronologia" not in TABLA_POR_TIPO


def test_la_cronologia_junta_eventos_ordena_y_trae_nacimientos(
    almacen: Almacen, id_obra: str
) -> None:
    ines = _ficha(
        almacen, id_obra, "Personaje", {"nombre": "Ines", "fechas": {"nacimiento": "1551"}}
    )
    fantasma = "per_ffffffff"
    almacen.guardar(
        [
            Artefacto(
                "EventoEstado",
                {
                    "tipo_de_evento": "viaja_a",
                    "fecha_resultante": "1587-04-03",
                    "lugar_resultante": "lug_1182",
                    "presentes": [ines, fantasma],
                },
                id_obra=id_obra,
                capitulo=2,
            ),
            Artefacto(
                "EventoEstado",
                {"tipo_de_evento": "transcurre_tiempo"},
                id_obra=id_obra,
                capitulo=1,
            ),
            Artefacto(
                "Evento",
                {"descripcion": "Auto de fe", "momento": "1587", "participantes": [ines]},
                id_obra=id_obra,
            ),
        ]
    )

    sucesos = almacen.cronologia(id_obra)

    assert [s["suceso"] for s in sucesos] == ["Auto de fe", "viaja_a", "transcurre_tiempo"]
    assert sucesos[0]["origen"] == "evento_del_mundo"
    assert sucesos[0]["capitulo"] is None
    viaje = sucesos[1]
    assert viaje["momento"] == "1587-04-03"
    assert viaje["lugar"] == "lug_1182"
    assert viaje["presentes"] == [
        {"id": ines, "nombre": "Ines", "nacimiento": "1551"},
        {"id": fantasma, "nombre": None, "nacimiento": None},
    ]
    assert sucesos[2]["momento"] is None, "lo que no trae momento va al final"


# --- RF-87. Dos rutas de lectura -------------------------------------------


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[TestClient]:
    app = crear_aplicacion(tmp_path / "api.sqlite3", ejecutor=EjecutorFingido())
    with TestClient(app) as cliente:
        yield cliente
        for hilo in cliente.app.state.produccion.hilos.values():  # type: ignore[attr-defined]
            hilo.join(timeout=60)


def _obra_terminada(cliente: TestClient) -> str:
    id_obra = cliente.post("/obras", json=BRIEF).json()["id_obra"]
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=60)
    assert not hilo.is_alive()
    return str(id_obra)


def test_la_api_sirve_los_hechos_con_sus_capitulos(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)

    hechos = cliente.get(f"/obras/{id_obra}/hechos").json()
    assert {h["nombre"] for h in hechos} == {"Ines de Salcedo", "Sevilla"}
    assert all(h["capitulos"] == [1, 2] for h in hechos)

    solo_lugares = cliente.get(f"/obras/{id_obra}/hechos", params={"tipo": "Lugar"}).json()
    assert [h["nombre"] for h in solo_lugares] == ["Sevilla"]
    canon = cliente.get(f"/obras/{id_obra}/hechos", params={"licencia": "canon"}).json()
    assert [h["nombre"] for h in canon] == ["Sevilla"]


def test_un_filtro_fuera_de_vocabulario_se_rechaza(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)
    respuesta = cliente.get(f"/obras/{id_obra}/hechos", params={"licencia": "inventada"})
    assert respuesta.status_code == 422


def test_los_filtros_de_la_api_son_los_vocabularios() -> None:
    """El borde repite los valores cerrados como tipo: tienen que coincidir."""
    from novela.api import aplicacion

    firma = aplicacion.crear_aplicacion().openapi()["paths"]["/obras/{id_obra}/hechos"]
    parametros = {p["name"]: p["schema"] for p in firma["get"]["parameters"]}
    tipos = parametros["tipo"]["anyOf"][0]["enum"]
    licencias = parametros["licencia"]["anyOf"][0]["enum"]
    assert tuple(tipos) == HECHOS_DE_LA_BIBLIA
    assert tuple(licencias) == LICENCIA


def test_la_api_sirve_la_cronologia(cliente: TestClient) -> None:
    id_obra = _obra_terminada(cliente)

    cronologia = cliente.get(f"/obras/{id_obra}/cronologia").json()

    assert cronologia["id_obra"] == id_obra
    assert [s["capitulo"] for s in cronologia["sucesos"]] == [1, 2]
    assert [s["momento"] for s in cronologia["sucesos"]] == ["1587-04-01", "1587-04-02"]
    presentes = cronologia["sucesos"][0]["presentes"]
    assert [(p["nombre"], p["nacimiento"]) for p in presentes] == [("Ines de Salcedo", "1551")]


def test_las_rutas_nuevas_son_de_lectura(cliente: TestClient) -> None:
    assert operaciones_de_escritura(cliente.app) == [  # type: ignore[arg-type]
        "POST /obras",
        "POST /obras/{id_obra}/detener",
        "POST /obras/{id_obra}/reanudar",
    ]


def test_una_obra_que_no_existe_da_404(cliente: TestClient) -> None:
    assert cliente.get("/obras/obr_00000000/hechos").status_code == 404
    assert cliente.get("/obras/obr_00000000/cronologia").status_code == 404


# --- RF-88. El recorrido en seco deja menciones y cronologia ---------------


def test_cerrar_un_capitulo_deja_sus_menciones_y_su_suceso(tmp_path: Path) -> None:
    almacen = abrir_almacen(tmp_path / "seco.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)

    informe = caminante.caminar_capitulo(id_obra, 1)

    assert informe.estado == "cerrado"
    menciones = almacen.listar("Mencion", id_obra)
    assert {m.procedencia_rol for m in menciones} == {"archivero"}
    assert len(menciones) == 2
    assert all(m.capitulo == 1 for m in menciones)
    [suceso] = almacen.cronologia(id_obra)
    assert suceso["capitulo"] == 1
    assert suceso["presentes"][0]["nacimiento"] == "1551"
    almacen.cerrar()
