"""SPEC1 4.19: lo que dice donde va un artefacto y el testigo del Planificador.

Metodo: `prueba`. Se siembra lo que hizo el modelo de verdad en la primera obra
y el ejecutor fingido no hacia: un Planificador que no escribe el `Capitulo`
(RF-180), que pone en sus escenas un estado fuera de vocabulario y el numero de
otro capitulo (RF-181), y que no deja escenas o las deja malformadas (RF-182).
Evidencia: los recuentos por capitulo en el almacen, el motivo de la detencion
y las trazas de cada intento de `planificar`.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.nucleo.caminante import Caminante, Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana

BRIEF = {
    "titulo": "El reloj de la aduana",
    "epoca": "Cadiz, 1810",
    "premisa": "Un relojero en la ciudad sitiada",
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 2,
}


@dataclass
class PlanificadorComoElModelo:
    """El fingido de siempre, con el Planificador cambiado.

    `sin_capitulo` quita el `Capitulo` del plan. `estado_de_escena` y
    `capitulo_de_escena` sobrescriben lo que cada escena dice de si misma.
    `vacios` es cuantas veces seguidas devuelve un plan sin escenas antes de
    devolver el bueno. `compromiso_malformado` añade un `Compromiso` con un
    estado fuera de vocabulario, que el almacen rechaza.
    """

    sin_capitulo: bool = False
    estado_de_escena: str | None = None
    capitulo_de_escena: int | None = None
    vacios: int = 0
    compromiso_malformado: bool = False
    interno: EjecutorFingido = field(default_factory=EjecutorFingido)
    _planes: int = 0

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        resultado = self.interno.ejecutar(encargo, ventana)
        if encargo.tarea != "planificar":
            return resultado
        self._planes += 1
        if self._planes <= self.vacios:
            return Resultado(
                artefactos=[a for a in resultado.artefactos if a.tipo != "Escena"],
                salida="plan sin escenas",
            )
        artefactos = [
            a for a in resultado.artefactos if not (self.sin_capitulo and a.tipo == "Capitulo")
        ]
        for artefacto in artefactos:
            if artefacto.tipo == "Escena":
                if self.estado_de_escena is not None:
                    artefacto.estado = self.estado_de_escena
                if self.capitulo_de_escena is not None:
                    artefacto.capitulo = self.capitulo_de_escena
        if self.compromiso_malformado:
            artefactos.append(
                Artefacto("Compromiso", {"setup": "el reloj parado"}, estado="abierta")
            )
        return Resultado(artefactos=artefactos, salida=resultado.salida)


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "testigo.sqlite3")
    yield almacen
    almacen.cerrar()


def _caminar(almacen: Almacen, ejecutor: object) -> str:
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())  # type: ignore[arg-type]
    caminante.caminar_obra(id_obra, 2)
    return id_obra


def _criticas_de_malformado(almacen: Almacen, id_obra: str) -> list[Artefacto]:
    return [
        c
        for c in almacen.listar("Critica", id_obra)
        if c.cuerpo.get("accion_sugerida") == "volver a escribir el artefacto con su esquema"
    ]


# --- RF-180: el `Capitulo` lo abre el backend ------------------------------


def test_sin_capitulo_del_planificador_el_backend_lo_abre_y_se_cierra(
    almacen: Almacen,
) -> None:
    id_obra = _caminar(almacen, PlanificadorComoElModelo(sin_capitulo=True))

    assert not almacen.esta_detenida(id_obra)
    assert almacen.ultimo_capitulo_cerrado(id_obra) == 2
    for numero in (1, 2):
        capitulos = almacen.listar("Capitulo", id_obra, capitulo=numero)
        assert [c.estado for c in capitulos] == ["cerrado"], "uno vivo, y cerrado"
        assert capitulos[0].procedencia_rol is None, "lo escribio el backend"


def test_si_el_planificador_abre_el_capitulo_el_backend_no_abre_otro(
    almacen: Almacen,
) -> None:
    id_obra = _caminar(almacen, PlanificadorComoElModelo())

    for numero in (1, 2):
        capitulos = almacen.listar("Capitulo", id_obra, capitulo=numero)
        assert len(capitulos) == 1
        assert capitulos[0].procedencia_rol == "planificador"
        assert capitulos[0].estado == "cerrado"


# --- RF-181: donde va y en que punto esta lo pone el backend ---------------


def test_el_estado_y_el_capitulo_de_una_escena_no_los_decide_el_rol(
    almacen: Almacen,
) -> None:
    """Lo que paso en el capitulo 2: `planificada` y el numero del anterior."""
    ejecutor = PlanificadorComoElModelo(estado_de_escena="planificada", capitulo_de_escena=1)
    id_obra = _caminar(almacen, ejecutor)

    assert not almacen.esta_detenida(id_obra)
    assert _criticas_de_malformado(almacen, id_obra) == []
    for numero in (1, 2):
        assert len(almacen.listar("Escena", id_obra, capitulo=numero)) == 3
    capitulos_con_texto = {b.capitulo for b in almacen.manuscrito_aceptado(id_obra)}
    assert capitulos_con_texto == {1, 2}


def test_en_un_encargo_de_la_obra_el_capitulo_del_artefacto_se_respeta(
    almacen: Almacen,
) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())
    critica = Artefacto("Critica", {"objeto": "capitulo 1"}, capitulo=1, estado="abierta")
    auditar = Encargo(
        paso=0,
        tarea="auditar",
        rol="arquitecto_de_arcos",
        unidad="obra",
        proyeccion=(),
        id_obra=id_obra,
        capitulo=2,
    )

    caminante._preparar(auditar, Resultado(artefactos=[critica]), "trz_x", 1)

    assert critica.capitulo == 1, "una critica global apunta a cualquier capitulo"
    assert critica.estado == "abierta", "el estado de una critica es del rol"


# --- RF-216: la escena la pone el backend ----------------------------------


def _encargo(id_obra: str, unidad: str, tarea: str = "verificar",
             escena: str | None = None) -> Encargo:
    rol = "planificador" if tarea == "planificar" else "verificador_de_continuidad"
    return Encargo(paso=6, tarea=tarea, rol=rol, unidad=unidad,
                   proyeccion=(), id_obra=id_obra, capitulo=1, escena=escena)


def test_una_escena_inventada_en_un_encargo_de_capitulo_se_quita(almacen: Almacen) -> None:
    """Lo que detuvo una obra real: una critica a `esc_0007`, que no existia."""
    id_obra = almacen.crear_obra(BRIEF)
    [de_verdad] = almacen.guardar([Artefacto("Escena", {"pov": "per_1"}, id_obra=id_obra,
                                             capitulo=1, orden=1, estado="planificado")])
    caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())
    inventada = Artefacto("Critica", {"objeto": "x"}, escena="esc_0007", estado="abierta")
    buena = Artefacto("Critica", {"objeto": "y"}, escena=de_verdad, estado="abierta")

    caminante._preparar(_encargo(id_obra, "capitulo"), Resultado(artefactos=[inventada, buena]),
                        "trz_x", 1)

    assert inventada.escena is None, "queda del capitulo, sin escena"
    assert buena.escena == de_verdad, "una escena del capitulo se respeta"


def test_en_un_encargo_de_escena_la_escena_es_la_del_encargo(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())
    critica = Artefacto("Critica", {"objeto": "x"}, escena="esc_0007", estado="abierta")

    caminante._preparar(_encargo(id_obra, "escena", escena="esc_real"),
                        Resultado(artefactos=[critica]), "trz_x", 1)

    assert critica.escena == "esc_real"


def test_el_planificador_crea_sus_escenas_y_no_se_le_quitan(almacen: Almacen) -> None:
    """Sus escenas nacen en la misma entrega: aun no estan en el almacen."""
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())
    beat = Artefacto("Beat", {"texto": "x"}, escena="esc_nueva")

    caminante._preparar(_encargo(id_obra, "capitulo", tarea="planificar"),
                        Resultado(artefactos=[beat]), "trz_x", 1)

    assert beat.escena == "esc_nueva"


# --- RF-182: planificar sin escenas es un intento fallido -----------------


def test_un_plan_sin_escenas_se_reintenta_y_no_deja_critica(almacen: Almacen) -> None:
    id_obra = _caminar(almacen, PlanificadorComoElModelo(vacios=1))

    assert not almacen.esta_detenida(id_obra)
    assert almacen.ultimo_capitulo_cerrado(id_obra) == 2
    assert _criticas_de_malformado(almacen, id_obra) == []
    del_primero = [
        (t.propias["intento"], t.cuerpo["salida"].startswith("fallo:"))
        for t in almacen.listar_trazas(id_obra, tarea="planificar")
        if t.capitulo == 1
    ]
    assert del_primero == [(1, True), (2, False)]
    assert len(almacen.listar("Plan", id_obra, capitulo=1)) == 1, "el fallido no escribio"


def test_un_plan_sin_escenas_agotado_detiene_la_obra(almacen: Almacen) -> None:
    id_obra = _caminar(almacen, PlanificadorComoElModelo(vacios=99))

    assert almacen.esta_detenida(id_obra)
    motivo = almacen.motivo_de_la_detencion(id_obra) or ""
    assert "planificar" in motivo and "intento 2" in motivo
    assert "ninguna Escena" in motivo
    assert almacen.listar("Plan", id_obra) == [], "nada a medio escribir"
    assert almacen.listar("Borrador", id_obra) == []
    assert almacen.auditada_hasta(id_obra) == 0, "no se audita una obra vacia"


def test_un_plan_rechazado_es_un_intento_fallido_y_no_una_critica(
    almacen: Almacen,
) -> None:
    id_obra = _caminar(almacen, PlanificadorComoElModelo(compromiso_malformado=True))

    assert almacen.esta_detenida(id_obra)
    motivo = almacen.motivo_de_la_detencion(id_obra) or ""
    assert "rechazo el plan" in motivo and "abierta" in motivo
    assert _criticas_de_malformado(almacen, id_obra) == []
    assert almacen.listar("Escena", id_obra) == [], "el lote entra entero o no entra"
