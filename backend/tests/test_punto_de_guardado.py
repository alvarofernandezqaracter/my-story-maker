"""SPEC1 4.10: el punto de guardado por capitulo y el limite de reintentos.

Metodo: `prueba`. La caida se siembra: un ejecutor que, en la tarea elegida,
lanza una excepcion que no es `Exception` —como muere un proceso, sin que nadie
la recoja— y deja la traza abierta y el capitulo a medias. Despues otro
caminante, que hace de proceso nuevo, reanuda la obra. Se comprueba que ni
duplica ni pierde (RF-92), que el cierre es una sola transaccion (RF-90), que
la auditoria tiene su propio punto de guardado (RF-94), que al arrancar se
relanza lo que se cayo (RF-93) y que cada politica de agotamiento hace lo que
su paso declara (RF-95 a RF-99). Evidencia: los recuentos por capitulo en el
almacen y las trazas de cada intento.
"""

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen, Artefacto, EscrituraProhibida, esquema
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.conexion import abrir, escritura
from novela.almacen.indice import Indice
from novela.almacen.migraciones import MIGRACIONES, aplicar
from novela.api.aplicacion import crear_aplicacion
from novela.nucleo import guion
from novela.nucleo.caminante import Caminante, Resultado
from novela.nucleo.guion import Encargo, GuionInvalido
from novela.nucleo.proyecciones import Ventana
from novela.vocabularios import AL_AGOTARSE

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "arcos": ["Ines pasa del miedo al desafio"],
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 2,
}


class Caida(BaseException):
    """El proceso muere: no es un fallo de la tarea, y nada la recoge."""


@dataclass
class EjecutorQueFalla:
    """El fingido de siempre, con una averia sembrada en una tarea concreta.

    `caida` tumba el proceso la vez `vez` que se llega a esa tarea en ese
    capitulo. `falla` hace que la tarea devuelva error en todos sus intentos.
    """

    caida: tuple[str, int] | None = None
    vez: int = 1
    falla: tuple[str, str | None] | None = None
    interno: EjecutorFingido = field(default_factory=EjecutorFingido)
    _vistas: int = 0

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        if self.caida == (encargo.tarea, encargo.capitulo):
            self._vistas += 1
            if self._vistas == self.vez:
                raise Caida(f"se cae la maquina en {encargo.tarea}")
        if self.falla is not None and self.falla[0] == encargo.tarea and (
            self.falla[1] is None or self.falla[1] == encargo.dimension
        ):
            raise RuntimeError(f"el proveedor no contesta a {encargo.tarea}")
        return self.interno.ejecutar(encargo, ventana)


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "guardado.sqlite3")
    yield almacen
    almacen.cerrar()


def _caminante(almacen: Almacen, ejecutor: object, indice: Indice | None = None) -> Caminante:
    return Caminante(almacen, ejecutor, catalogo=CatalogoFingido(), indice=indice)  # type: ignore[arg-type]


def _huella(almacen: Almacen, id_obra: str) -> dict[str, object]:
    """Lo que tiene que quedar igual pase lo que pase: una cosa de cada por
    capitulo cerrado, y el manuscrito."""
    por_capitulo = {}
    for numero in (1, 2):
        por_capitulo[numero] = {
            "capitulos": len(almacen.listar("Capitulo", id_obra, capitulo=numero)),
            "eventos": len(almacen.eventos_del_capitulo(id_obra, numero)),
            "resumenes": len(almacen.listar("ResumenCapitulo", id_obra, capitulo=numero)),
            "escenas": len(almacen.listar("Escena", id_obra, capitulo=numero)),
            "estado": almacen.estado_en(id_obra, numero) is not None,
        }
    return {
        "por_capitulo": por_capitulo,
        "manuscrito": [
            (b.capitulo, b.cuerpo["texto"]) for b in almacen.manuscrito_aceptado(id_obra)
        ],
        "auditada_hasta": almacen.auditada_hasta(id_obra),
    }


def _obra_sin_cortes(tmp_path: Path) -> dict[str, object]:
    almacen = abrir_almacen(tmp_path / "sin_cortes.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)
    _caminante(almacen, EjecutorFingido()).caminar_obra(id_obra, 2)
    huella = _huella(almacen, id_obra)
    almacen.cerrar()
    return huella


# --- RF-90 a RF-92: se cae en cualquier punto, y ni duplica ni pierde ------

PUNTOS_DE_CAIDA = [
    ("planificar", 2, 1),
    ("documentar", 2, 2),
    ("redactar", 2, 1),
    ("verificar", 2, 3),
    ("editar_estilo", 2, 1),
    ("plegar", 2, 1),
    ("destilar", 2, 1),
    ("auditar", 2, 3),
]


@pytest.mark.parametrize(("tarea", "capitulo", "vez"), PUNTOS_DE_CAIDA)
def test_una_caida_en_cualquier_punto_ni_duplica_ni_pierde(
    tmp_path: Path, almacen: Almacen, tarea: str, capitulo: int, vez: int
) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    with pytest.raises(Caida):
        _caminante(almacen, EjecutorQueFalla(caida=(tarea, capitulo), vez=vez)).caminar_obra(
            id_obra, 2
        )
    assert almacen.trazas_abiertas(id_obra), "la caida tenia que dejar una traza abierta"
    antes = [(b.capitulo, b.cuerpo["texto"]) for b in almacen.manuscrito_aceptado(id_obra)]
    cerrado_antes = almacen.ultimo_capitulo_cerrado(id_obra)

    # Un proceso nuevo, con un ejecutor sano, reanuda la obra.
    _caminante(almacen, EjecutorFingido()).caminar_obra(id_obra, 2)

    assert _huella(almacen, id_obra) == _obra_sin_cortes(tmp_path)
    assert [u for u in _huella(almacen, id_obra)["manuscrito"] if u[0] <= cerrado_antes] == [  # type: ignore[union-attr]
        u for u in antes if u[0] <= cerrado_antes
    ], "lo cerrado antes de la caida tiene que seguir igual"
    assert not almacen.trazas_abiertas(id_obra)
    interrumpidas = [
        t for t in almacen.listar_trazas(id_obra) if t.cuerpo.get("salida") == "interrumpida"
    ]
    assert len(interrumpidas) == 1


def test_antes_del_commit_del_cierre_no_existe_nada_del_cierre(almacen: Almacen) -> None:
    """RF-90: se cae en `destilar`, con `plegar` ya terminado."""
    id_obra = almacen.crear_obra(BRIEF | {"capitulos_objetivo": 1})
    with pytest.raises(Caida):
        _caminante(almacen, EjecutorQueFalla(caida=("destilar", 1))).caminar_obra(id_obra, 1)

    assert almacen.eventos_del_capitulo(id_obra, 1) == []
    assert almacen.estado_en(id_obra, 1) is None
    assert almacen.listar("ResumenCapitulo", id_obra) == []
    assert almacen.ultimo_capitulo_cerrado(id_obra) == 0


def test_lo_descartado_sale_del_indice(almacen: Almacen) -> None:
    """RF-91 y RF-64: lo del capitulo que no cerro no vuelve como eco."""
    indice = Indice(almacen)
    id_obra = almacen.crear_obra(BRIEF)
    with pytest.raises(Caida):
        _caminante(almacen, EjecutorQueFalla(caida=("plegar", 2)), indice).caminar_obra(
            id_obra, 2
        )
    assert _fragmentos_del_capitulo(almacen, id_obra, 2) > 0, "la prosa aceptada ya se indexo"

    _caminante(almacen, EjecutorFingido(), indice).volver_al_punto_de_guardado(id_obra)

    assert _fragmentos_del_capitulo(almacen, id_obra, 2) == 0
    assert _fragmentos_del_capitulo(almacen, id_obra, 1) > 0
    vivos = {b.id for b in almacen.listar("Borrador", id_obra)} | {
        a.id
        for tipo in ("Fuente", "Escena", "ResumenCapitulo")
        for a in almacen.listar(tipo, id_obra)
    }
    for fila in almacen._lector.execute(
        "SELECT artefacto FROM fragmento WHERE id_obra = ?", (id_obra,)
    ):
        assert fila["artefacto"] in vivos, "un fragmento apunta a algo descartado"


def _fragmentos_del_capitulo(almacen: Almacen, id_obra: str, capitulo: int) -> int:
    fila = almacen._lector.execute(
        "SELECT COUNT(*) AS n FROM fragmento WHERE id_obra = ? AND capitulo = ?",
        (id_obra, capitulo),
    ).fetchone()
    return int(fila["n"])


# --- RF-94: la auditoria tiene su punto de guardado ------------------------


def test_la_auditoria_de_cierre_corre_una_sola_vez_aunque_se_caiga(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    with pytest.raises(Caida):
        _caminante(almacen, EjecutorQueFalla(caida=("auditar", 2), vez=4)).caminar_obra(
            id_obra, 2
        )
    assert almacen.auditada_hasta(id_obra) == 0

    sano = EjecutorFingido()
    _caminante(almacen, sano).caminar_obra(id_obra, 2)
    assert almacen.auditada_hasta(id_obra) == 2
    auditorias = [e for e in sano.llamadas if e.tarea == "auditar"]
    assert len(auditorias) == len(guion.CRIBAS["global"]), "se audita una vez, entera"

    otra_vez = EjecutorFingido()
    _caminante(almacen, otra_vez).caminar_obra(id_obra, 2)
    assert otra_vez.llamadas == [], "una obra terminada no vuelve a gastar nada"


# --- RF-93: al arrancar se relanza lo que se cayo --------------------------


def test_al_arrancar_se_relanza_la_obra_caida_y_no_las_demas(tmp_path: Path) -> None:
    ruta = tmp_path / "arranque.sqlite3"
    almacen = abrir_almacen(ruta)
    caida = almacen.crear_obra(BRIEF | {"capitulos_objetivo": 1})
    with pytest.raises(Caida):
        _caminante(almacen, EjecutorQueFalla(caida=("redactar", 1))).caminar_obra(caida, 1)
    detenida = almacen.crear_obra(BRIEF | {"capitulos_objetivo": 1})
    almacen.detener(detenida, "orden del editor")
    terminada = almacen.crear_obra(BRIEF | {"capitulos_objetivo": 1})
    _caminante(almacen, EjecutorFingido()).caminar_obra(terminada, 1)
    almacen.cerrar()

    app = crear_aplicacion(ruta, ejecutor=EjecutorFingido())
    with TestClient(app) as cliente:
        produccion = cliente.app.state.produccion  # type: ignore[attr-defined]
        assert set(produccion.hilos) == {caida}
        produccion.hilos[caida].join(timeout=60)
        ficha = cliente.get(f"/obras/{caida}").json()
        assert ficha["capitulos_cerrados"] == 1
        assert produccion.almacen.auditada_hasta(caida) == 1


# --- RF-95 a RF-97: el tope y la politica estan escritos en el guion --------


def test_todo_paso_declara_su_tope_y_su_politica() -> None:
    for paso in (*guion.PASOS, *guion.FUERA_DEL_GUION.values()):
        assert paso.reintentos >= 1
        assert paso.al_agotarse in AL_AGOTARSE


def test_la_politica_de_cada_paso_es_la_de_la_spec() -> None:
    """RF-97: detener lo que produce testigo, critica para lo que comprueba y
    seguir para documentar."""
    por_paso = {paso.numero: paso.al_agotarse for paso in guion.PASOS}
    assert por_paso == {
        1: "detener_obra",
        2: "seguir",
        3: "detener_obra",
        4: "critica_abierta",
        5: "detener_obra",
        6: "critica_abierta",
        7: "detener_obra",
        8: "critica_abierta",
        9: "detener_obra",
        10: "detener_obra",
    }
    assert guion.FUERA_DEL_GUION["poblar_mundo"].al_agotarse == "detener_obra"
    assert guion.FUERA_DEL_GUION["auditar"].al_agotarse == "critica_abierta"
    assert {paso.reintentos for paso in (*guion.PASOS, *guion.FUERA_DEL_GUION.values())} == {2}


@pytest.mark.parametrize(
    "roto",
    [
        {"reintentos": 2},
        {"al_agotarse": "detener_obra"},
        {"reintentos": 0, "al_agotarse": "detener_obra"},
        {"reintentos": 2, "al_agotarse": "improvisar"},
    ],
)
def test_un_paso_sin_tope_o_sin_politica_no_carga(roto: dict[str, object]) -> None:
    paso = {
        "numero": 1,
        "tarea": "planificar",
        "rol": "planificador",
        "concurrencia": "solo",
        "unidad": "capitulo",
        "proyeccion": [],
    } | roto
    with pytest.raises(GuionInvalido):
        guion._a_paso(paso)


# --- RF-96, RF-98 y RF-99: lo que pasa al agotarse -------------------------


def test_una_tarea_que_produce_testigo_detiene_la_obra(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    _caminante(almacen, EjecutorQueFalla(falla=("redactar", None))).caminar_obra(id_obra, 2)

    assert almacen.esta_detenida(id_obra)
    motivo = almacen._lector.execute(
        "SELECT motivo FROM control_de_ejecucion WHERE id_obra = ?", (id_obra,)
    ).fetchone()["motivo"]
    assert "redactar" in motivo and "intento 2" in motivo
    assert almacen.listar("Borrador", id_obra) == [], "nada a medio escribir"
    fallidas = [t for t in almacen.listar_trazas(id_obra, tarea="redactar")]
    assert [t.propias["intento"] for t in fallidas] == [1, 2]
    assert all(t.cuerpo["salida"].startswith("fallo:") for t in fallidas)


def test_una_comprobacion_agotada_deja_una_critica_y_la_obra_sigue(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    ejecutor = EjecutorQueFalla(falla=("verificar", "integridad_de_pov"))
    _caminante(almacen, ejecutor).caminar_obra(id_obra, 2)

    assert not almacen.esta_detenida(id_obra)
    assert almacen.ultimo_capitulo_cerrado(id_obra) == 2
    no_comprobadas = [
        c
        for c in almacen.listar("Critica", id_obra, dimension="integridad_de_pov")
        if c.cuerpo["evidencia"].startswith("no comprobado")
    ]
    assert no_comprobadas
    for critica in no_comprobadas:
        assert critica.severidad == "bloqueante"
        assert critica.estado == "abierta", "no se enruta: se queda abierta"
        assert "trz_" in critica.cuerpo["evidencia"], "la evidencia es la traza"
        assert critica.cuerpo["detectada_por"]["rol"] is None


def test_documentar_agotado_sigue_sin_critica(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    _caminante(almacen, EjecutorQueFalla(falla=("documentar", None))).caminar_obra(id_obra, 2)

    assert not almacen.esta_detenida(id_obra)
    assert almacen.ultimo_capitulo_cerrado(id_obra) == 2
    assert almacen.listar("Fuente", id_obra) == []
    criticas = almacen.listar("Critica", id_obra)
    assert not any(c.cuerpo["evidencia"].startswith("no comprobado") for c in criticas)


def test_el_contador_vuelve_a_empezar_con_el_capitulo(almacen: Almacen) -> None:
    """RF-98: la tarea que corto la caida no cuenta, y al rehacer el capitulo
    cada encargo empieza por el intento 1."""
    id_obra = almacen.crear_obra(BRIEF | {"capitulos_objetivo": 1})
    with pytest.raises(Caida):
        _caminante(almacen, EjecutorQueFalla(caida=("planificar", 1))).caminar_obra(id_obra, 1)
    _caminante(almacen, EjecutorFingido()).caminar_obra(id_obra, 1)

    planes = almacen.listar_trazas(id_obra, tarea="planificar")
    assert [(t.propias["intento"], t.cuerpo["salida"]) for t in planes] == [
        (1, "interrumpida"),
        (1, "plan escrito"),
    ]


# --- D-32: marcar no es modificar -----------------------------------------


@pytest.mark.parametrize("tipo", esquema.TIPOS_INMUTABLES)
def test_a_un_inmutable_se_le_pone_la_marca_una_vez_y_nada_mas(
    almacen: Almacen, tipo: str
) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    identificador = almacen.guardar(
        [Artefacto(tipo, {"nota": "x"}, id_obra=id_obra, capitulo=1)]
    )[0]
    almacen._actualizar(tipo, identificador, {"caducado_en": "2026-01-01"})
    with pytest.raises(EscrituraProhibida):
        almacen._actualizar(tipo, identificador, {"caducado_en": None})
    with pytest.raises(EscrituraProhibida):
        almacen._actualizar(tipo, identificador, {"cuerpo": '{"nota": "otra"}'})


def test_un_borrador_aceptado_admite_la_marca_y_nada_mas(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    identificador = almacen.guardar_borrador(
        Artefacto("Borrador", {"texto": "x"}, id_obra=id_obra, capitulo=1, escena="esc_1")
    )
    almacen.aceptar_borrador(identificador)
    almacen._actualizar("Borrador", identificador, {"caducado_en": "2026-01-01"})
    with pytest.raises(EscrituraProhibida):
        almacen.descartar_borrador(identificador)


# --- La migracion 4, sobre una base que ya existia ------------------------


def test_la_migracion_da_por_auditado_lo_ya_cerrado(tmp_path: Path) -> None:
    ruta = tmp_path / "vieja.sqlite3"
    conexion = abrir(ruta)
    for numero, nombre, sentencias in MIGRACIONES[:3]:
        with escritura(conexion):
            for sentencia in sentencias():
                conexion.execute(sentencia)
            conexion.execute(
                "INSERT INTO migracion (numero, nombre, aplicada_en) VALUES (?, ?, 'x')",
                (numero, nombre),
            )
    with escritura(conexion):
        conexion.execute(
            "INSERT INTO artefacto_obra (id, id_obra, tipo, cuerpo, memoria, creado_en) "
            "VALUES ('obr_1', 'obr_1', 'Obra', '{}', 'obra', 'x')"
        )
        conexion.execute(
            "INSERT INTO control_de_ejecucion (id_obra, detenida, actualizado_en) "
            "VALUES ('obr_1', 0, 'x')"
        )
        conexion.execute(
            "INSERT INTO artefacto_capitulo (id, id_obra, tipo, cuerpo, capitulo, estado, "
            "memoria, creado_en) VALUES ('cap_1', 'obr_1', 'Capitulo', '{}', 1, 'cerrado', "
            "'obra', 'x')"
        )
        conexion.execute(
            "INSERT INTO artefacto_evento_estado (id, id_obra, tipo, cuerpo, capitulo, "
            "memoria, creado_en) "
            "VALUES ('evt_1', 'obr_1', 'EventoEstado', '{}', 1, 'obra', 'x')"
        )

    assert aplicar(conexion) == len(MIGRACIONES)

    fila = conexion.execute(
        "SELECT auditada_hasta FROM control_de_ejecucion WHERE id_obra = 'obr_1'"
    ).fetchone()
    assert fila["auditada_hasta"] == 1
    conexion.execute("UPDATE artefacto_evento_estado SET caducado_en = 'y' WHERE id = 'evt_1'")
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        conexion.execute("UPDATE artefacto_evento_estado SET cuerpo = '[]' WHERE id = 'evt_1'")
    conexion.close()
