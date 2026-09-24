"""Etapa 3: el recorrido en seco. La puerta.

Metodo: `demostracion`, mas una `prueba` por rol que intenta la escritura
prohibida y falla. Es la unica comprobacion que ejercita el sistema entero sin
gastar ni producir novela: con un ejecutor fingido que devuelve artefactos
preparados, el guion recorre los diez pasos de un capitulo de tres escenas,
cada paso encarga su tarea al rol que le toca, ningun rol escribe una entidad
que no le corresponde, las tandas respetan la anchura calculada y todo lo
producido se puede volver a servir.

Mientras esto no este en verde no se invoca a ningun agente real.
"""

from pathlib import Path

import pytest

from dobles import CasoSembrado, CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.nucleo import presupuesto
from novela.nucleo.caminante import Apunte, Caminante, Informe
from novela.nucleo.gobierno import QUIEN_ESCRIBE, EscrituraNoAutorizada
from novela.vocabularios import ROLES, TIPOS_DE_ARTEFACTO

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "arcos": ["Ines pasa del miedo al desafio"],
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 1,
}

# Un defecto por criba, para que el guion tenga que reaccionar: una bloqueante
# en la primera escena obliga a regenerar, y una mayor en la segunda obliga a
# una revision dirigida. Sin ellos, los pasos 3-repetido y 5 no llegarian a
# ejercitarse.
SEMBRADOS = [
    CasoSembrado(paso=4, indice_de_escena=0, dimension="integridad_de_pov",
                 severidad="bloqueante"),
    CasoSembrado(paso=6, indice_de_escena=1, dimension="anacronismo_material",
                 severidad="mayor"),
]


def _caminar(ruta: Path) -> tuple[Almacen, str, EjecutorFingido, Informe]:
    almacen = abrir_almacen(ruta)
    id_obra = almacen.crear_obra(BRIEF)
    ejecutor = EjecutorFingido(sembrados=list(SEMBRADOS))
    caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)
    informe = caminante.caminar_capitulo(id_obra, 1)
    return almacen, id_obra, ejecutor, informe


@pytest.fixture
def recorrido(tmp_path: Path) -> tuple[Almacen, str, EjecutorFingido, Informe]:
    almacen, id_obra, ejecutor, informe = _caminar(tmp_path / "seco.sqlite3")
    yield almacen, id_obra, ejecutor, informe
    almacen.cerrar()


def _normalizar(recorrido: list[Apunte]) -> list[tuple[int, str, str, int, int, str | None]]:
    """La misma secuencia con las escenas por su orden, no por su `id`."""
    orden: dict[str, int] = {}
    normalizado = []
    for apunte in recorrido:
        if apunte.escena and apunte.escena not in orden:
            orden[apunte.escena] = len(orden)
        normalizado.append(
            (
                apunte.paso,
                apunte.tarea,
                apunte.rol,
                apunte.tanda,
                orden.get(apunte.escena or "", -1),
                apunte.dimension,
            )
        )
    return normalizado


# --- Los diez pasos, cada uno a su rol -------------------------------------


def test_se_recorren_los_diez_pasos_del_guion(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    _, _, _, informe = recorrido
    pasos = sorted({apunte.paso for apunte in informe.recorrido})
    assert pasos == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_cada_paso_encarga_su_tarea_al_rol_que_le_toca(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    _, _, _, informe = recorrido
    por_paso = {
        (apunte.paso, apunte.rol) for apunte in informe.recorrido
    }
    assert (1, "planificador") in por_paso
    assert (2, "documentalista") in por_paso
    assert (3, "redactor") in por_paso
    assert (4, "verificador_de_continuidad") in por_paso
    assert (5, "revisor") in por_paso
    assert (6, "verificador_de_continuidad") in por_paso
    assert (7, "editor_de_estilo") in por_paso
    assert (9, "contable_de_estado") in por_paso
    assert (10, "archivero") in por_paso
    # La criba de pulido reparte entre tres roles, uno por dimension.
    assert {rol for paso, rol in por_paso if paso == 8} == {
        "verificador_de_continuidad",
        "editor_de_estilo",
        "juez_de_rubrica",
    }


def test_el_capitulo_termina_cerrado(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    _, _, _, informe = recorrido
    assert informe.estado == "cerrado"


# --- Las tandas respetan la anchura calculada ------------------------------


def test_ninguna_tanda_pasa_de_la_anchura_calculada(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    _, _, ejecutor, informe = recorrido
    por_tanda: dict[int, list[Apunte]] = {}
    for apunte in informe.recorrido:
        por_tanda.setdefault(apunte.tanda, []).append(apunte)
    for numero, apuntes in por_tanda.items():
        # Por rol y paso: el mismo rol cuesta mas abierto en un paso con hooks,
        # que reserva su vuelta de correccion (SPEC1 RF-128).
        pares = {(apunte.rol, apunte.paso) for apunte in apuntes}
        anchura = min(
            presupuesto.anchura_de_tanda(
                [e for e in ejecutor.llamadas if (e.rol, e.paso) == par][:1]
            )
            for par in pares
        )
        assert len(apuntes) <= anchura, f"la tanda {numero} se pasa de ancha"


def test_el_pico_de_contexto_concurrente_no_pasa_del_techo(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    almacen, id_obra, _, _ = recorrido
    assert almacen.trazas_abiertas(id_obra) == []
    assert almacen.contexto_de_entrada_abierto(id_obra) == 0


# --- Todo lo producido queda guardado y se puede volver a servir -----------


def test_todo_lo_producido_queda_guardado(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    almacen, id_obra, _, _ = recorrido
    assert len(almacen.listar("Escena", id_obra, capitulo=1)) == 3
    assert len(almacen.manuscrito_aceptado(id_obra)) == 3
    assert len(almacen.listar("EventoEstado", id_obra, capitulo=1)) == 1
    assert len(almacen.listar("ResumenCapitulo", id_obra, capitulo=1)) == 1
    assert almacen.estado_en(id_obra, 1) is not None
    assert len(almacen.listar("Personaje", id_obra)) == 1


def test_toda_tarea_dejo_traza(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    almacen, id_obra, ejecutor, _ = recorrido
    trazas = almacen.listar_trazas(id_obra)
    assert len(trazas) == len(ejecutor.llamadas)
    for traza in trazas:
        assert traza.propias["cerrada_en"] is not None
        assert traza.propias["tokens_de_entrada_estimados"] > 0
        assert "contexto_enviado" in traza.cuerpo


def test_la_memoria_de_capitulo_se_retira_al_cerrar(
    recorrido: tuple[Almacen, str, EjecutorFingido, Informe],
) -> None:
    almacen, id_obra, _, _ = recorrido
    assert almacen.listar("Critica", id_obra, capitulo=1) == []
    assert almacen.listar("Critica", id_obra, capitulo=1, incluir_caducados=True) != []


# --- El guion es reproducible -----------------------------------------------


def test_repetido_dos_veces_da_la_misma_secuencia(tmp_path: Path) -> None:
    """Misma obra y mismos artefactos dan la misma secuencia de pasos, tandas y
    proyecciones. Lo que varia es la salida del modelo, no el recorrido."""
    primera_almacen, _, primer_ejecutor, primera = _caminar(tmp_path / "una.sqlite3")
    segunda_almacen, _, segundo_ejecutor, segunda = _caminar(tmp_path / "otra.sqlite3")
    try:
        assert _normalizar(primera.recorrido) == _normalizar(segunda.recorrido)
        assert [e.proyeccion for e in primer_ejecutor.llamadas] == [
            e.proyeccion for e in segundo_ejecutor.llamadas
        ]
        assert [v.tokens for v in primer_ejecutor.ventanas] == [
            v.tokens for v in segundo_ejecutor.ventanas
        ]
    finally:
        primera_almacen.cerrar()
        segunda_almacen.cerrar()


# --- La escritura prohibida, rol por rol -----------------------------------


@pytest.mark.parametrize("rol", ROLES)
def test_ningun_rol_escribe_lo_que_no_le_asigna_la_tabla_de_gobierno(
    tmp_path: Path, rol: str
) -> None:
    """Se enumeran, rol por rol, las escrituras posibles y se intenta la
    prohibida. Es el guardarrail de verdad: no depende del prompt."""
    almacen = abrir_almacen(tmp_path / f"{rol}.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)
    prohibidos = [
        tipo
        for tipo in TIPOS_DE_ARTEFACTO
        if rol not in QUIEN_ESCRIBE.get(tipo, frozenset())
    ]
    assert prohibidos, f"{rol} no tiene ninguna escritura prohibida y eso es un defecto"

    for tipo in prohibidos:
        ejecutor = EjecutorFingido()
        caminante = Caminante(almacen, ejecutor)
        encargo_falso = _encargo_de(rol, id_obra)
        with pytest.raises(EscrituraNoAutorizada, match=tipo):
            caminante._guardar(
                encargo_falso,
                _resultado_con(tipo),
                id_traza="trz_00000000",
                intento=1,
            )
    almacen.cerrar()


def _encargo_de(rol: str, id_obra: str):
    from novela.nucleo.guion import Encargo
    from novela.vocabularios import TAREA_DE_ROL

    return Encargo(
        paso=0,
        tarea=TAREA_DE_ROL[rol],
        rol=rol,
        unidad="escena",
        proyeccion=(),
        id_obra=id_obra,
        capitulo=1,
    )


def _resultado_con(tipo: str):
    from novela.nucleo.caminante import Resultado

    return Resultado(artefactos=[Artefacto(tipo, {"nota": "no deberia entrar"})])
