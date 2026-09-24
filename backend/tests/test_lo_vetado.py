"""Lo vetado: tres listas, comparacion normalizada y registro (SPEC1 4.14, §10.10).

Cierre por `prueba`, sin gastar: la comparacion es una funcion pura y se le da
texto; el hook se alimenta con la entrada de Claude Code; y el recorrido con un
Redactor fingido, con el CLI interceptado, deja el registro que se sirve por la
API. Ninguna prueba cuenta cuantos terminos trae la lista global: se leen del
almacen.
"""

import json
import sqlite3
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dobles import CatalogoFingido, EjecutorFingido
from novela import ganchos
from novela.almacen import Almacen
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.esquema import TERMINOS_VETADOS_DE_SERIE
from novela.api.aplicacion import crear_aplicacion
from novela.ejecutor import EjecutorDeSubagentes, vetos_de
from novela.nucleo import guion
from novela.nucleo.caminante import Caminante, Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana, ensamblar
from novela.vocabularios import GANCHOS

TEMA = "muerte de animales"
PALABRA = "búho"

BRIEF: dict[str, Any] = {
    "titulo": "La imprenta de la calle Mayor",
    "epoca": "Madrid, 1808",
    "premisa": "Una aprendiz de impresor esconde pliegos prohibidos",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo"],
    "capitulos_objetivo": 1,
    "politicas_globales": {"pov": "tercera_limitada"},
    "arcos": ["Ines pasa del miedo al desafio"],
    "destinatario": {
        "nombre": "Marta",
        "edad": 9,
        "tono": "aventura luminosa",
        "dedicatoria": "Para Marta",
        "rasgos": [],
        "recuerdos": [],
        "vetos": [TEMA, PALABRA],
    },
}

SIN_DESTINATARIO = {k: v for k, v in BRIEF.items() if k != "destinatario"}


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "vetado.sqlite3")
    yield almacen
    almacen.cerrar()


def _global(almacen: Almacen) -> str:
    """Un termino de una palabra de la lista global, leido del almacen."""
    return next(t for t in almacen.terminos_vetados_globales() if " " not in t)


def _encargo_de_redactar(id_obra: str = "obr_1") -> Encargo:
    return guion.expandir(guion.paso(3), id_obra=id_obra, capitulo=1, escenas=("esc_1",))[0]


def _entrega(texto: str) -> str:
    return json.dumps(
        {
            "artefactos": [
                {
                    "tipo": "Borrador",
                    "cuerpo": {"texto": texto, "unidad": "esc_1", "cumple": ["objetivo"]},
                },
                {"tipo": "Parrafo", "cuerpo": {"texto": texto, "modo": "escena"}},
            ]
        },
        ensure_ascii=False,
    )


def _halladas(texto: str, vetos: list[ganchos.Veto | str]) -> list[tuple[str, str]]:
    return [(c.veto.nivel, c.encontrado) for c in ganchos.coincidencias(texto, vetos)]


# --- RF-131: la lista global viene de serie ----------------------------------


def test_la_lista_global_viene_sembrada_en_la_base(almacen: Almacen) -> None:
    assert almacen.terminos_vetados_globales() == sorted(TERMINOS_VETADOS_DE_SERIE)


def test_la_lista_global_ni_se_borra_ni_se_cambia(almacen: Almacen) -> None:
    termino = _global(almacen)
    with pytest.raises(sqlite3.IntegrityError):
        almacen._escritor.execute(
            "DELETE FROM termino_vetado_global WHERE termino = ?", (termino,)
        )
    with pytest.raises(sqlite3.IntegrityError):
        almacen._escritor.execute(
            "UPDATE termino_vetado_global SET termino = 'x' WHERE termino = ?", (termino,)
        )


def test_ninguna_ruta_edita_ni_sirve_la_lista_global(tmp_path: Path) -> None:
    app = crear_aplicacion(tmp_path / "api.sqlite3", ejecutor=EjecutorFingido())
    with TestClient(app) as cliente:
        rutas = cliente.get("/openapi.json").json()["paths"]
    assert not [ruta for ruta in rutas if "vetad" in ruta or "lista" in ruta]


# --- RF-130: tres listas, dos niveles, un caso por nivel ---------------------


def test_nivel_global_aplica_tambien_sin_destinatario(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(SIN_DESTINATARIO)
    ventana = ensamblar(almacen, _encargo_de_redactar(id_obra))
    assert ventana.vetos == ()
    termino = _global(almacen)
    texto = f"Y entonces grito: «{termino.upper()}»."
    assert _halladas(texto, list(vetos_de(ventana))) == [("global", termino.upper())]
    assert termino not in ventana.texto, "la lista no entra en la ventana (RF-134)"


def test_nivel_palabra_del_comprador(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    vetos = list(vetos_de(ensamblar(almacen, _encargo_de_redactar(id_obra))))
    assert ganchos.Veto(PALABRA, "palabra_del_comprador") in vetos
    assert _halladas("En la torre canto un búho.", vetos) == [
        ("palabra_del_comprador", "búho")
    ]


def test_nivel_tema_del_comprador_como_frase(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    vetos = list(vetos_de(ensamblar(almacen, _encargo_de_redactar(id_obra))))
    assert ganchos.Veto(TEMA, "tema_del_comprador") in vetos
    assert _halladas("Aquel invierno hubo muertes de animales.", vetos) == [
        ("tema_del_comprador", "muertes de animales")
    ]
    # Limite declarado (RF-133, D-52): el tema dicho con otras palabras no casa.
    assert _halladas("Aquel invierno mataron a los animales.", vetos) == []


def test_un_paso_sin_policy_no_lleva_ninguna_lista(almacen: Almacen) -> None:
    id_obra = almacen.crear_obra(BRIEF)
    encargo = guion.expandir(guion.paso(1), id_obra=id_obra, capitulo=1, escenas=())[0]
    ventana = ensamblar(almacen, encargo)
    assert (ventana.vetos, ventana.vetos_globales) == ((), ())


# --- RF-132: la normalizacion ------------------------------------------------


@pytest.mark.parametrize(
    ("veto", "escrito"),
    [
        ("búho", "Buho"),  # acento y mayuscula
        ("buho", "BÚHO"),  # el acento en el texto y no en el veto
        ("alguacil", "alguaciles"),  # plural en -es
        ("perro", "Perros"),  # plural en -s
        ("lápiz", "lápices"),  # plural en -ces
        ("tonto", "tontas"),  # genero y numero
        ("mierda", "mieeerda"),  # letra alargada
        ("pingüino", "pinguinos"),  # dieresis
    ],
)
def test_casan_las_variantes_simples(veto: str, escrito: str) -> None:
    assert _halladas(f"Dijo {escrito}, y se fue.", [veto]) == [
        ("palabra_del_comprador", escrito)
    ]


@pytest.mark.parametrize(
    ("veto", "texto"),
    [
        ("culo", "Vimos una película minúscula."),  # dentro de otra palabra
        ("coño", "Un cono de luz."),  # la ñ es otra letra
        ("mierda", "m i e r d a"),  # separada: limite declarado
    ],
)
def test_no_casa_lo_que_no_es_la_palabra(veto: str, texto: str) -> None:
    assert _halladas(texto, [veto]) == []


def test_el_motivo_nombra_lo_escrito_y_no_la_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    """RF-134: al agente le llega lo que el escribio, con su nivel en el entorno."""
    vetos = [ganchos.Veto("alguacil", "global")]
    monkeypatch.setenv(ganchos.VARIABLE_DE_VETOS, ganchos.vetos_para_el_entorno(vetos))
    monkeypatch.setenv(ganchos.VARIABLE_DE_RESERVA, "4000")
    entrada = json.dumps(
        {
            "last_assistant_message": _entrega("Llegaron los Alguaciles."),
            "stop_hook_active": False,
        }
    )
    codigo, _, motivo = ganchos.principal(["policy", "redactar"], entrada)
    assert codigo == ganchos.SALIDA_BLOQUEA
    assert "«Alguaciles»" in motivo and "«alguacil»" not in motivo


# --- RF-135 a RF-138: el registro, la detencion y la API ---------------------


def _flujo(primero: str, final: str, *, bloqueo: str | None) -> str:
    """Lo que devuelve `claude --print --output-format stream-json --verbose`:
    el mensaje del agente, el hook que lo bloquea y la entrega final."""

    def mensaje(texto: str) -> dict[str, Any]:
        return {"type": "assistant", "message": {"content": [{"type": "text", "text": texto}]}}

    lineas: list[dict[str, Any]] = [{"type": "system", "subtype": "init"}, mensaje(primero)]
    if bloqueo is not None:
        lineas += [
            {
                "type": "system",
                "subtype": "hook_response",
                "hook_event": "Stop",
                "exit_code": 2,
                "stdout": "",
                "stderr": bloqueo,
            },
            mensaje(final),
        ]
    lineas += [
        {
            "type": "system",
            "subtype": "hook_response",
            "hook_event": "Stop",
            "exit_code": 0,
            "stdout": f"{ganchos.PREFIJO}{gancho}] ya hubo vuelta: decide el ejecutor",
            "stderr": "",
        }
        for gancho in GANCHOS
    ]
    lineas.append(
        {"type": "result", "result": final, "is_error": False, "usage": {"input_tokens": 9}}
    )
    return "\n".join(json.dumps(linea, ensure_ascii=False) for linea in lineas)


@dataclass
class RedactorDeVerdad:
    """El fingido de siempre, salvo `redactar`, que pasa por el ejecutor real
    con el CLI interceptado."""

    interno: EjecutorFingido = field(default_factory=EjecutorFingido)
    real: EjecutorDeSubagentes = field(default_factory=EjecutorDeSubagentes)

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        if encargo.tarea != "redactar":
            return self.interno.ejecutar(encargo, ventana)
        return self.real.ejecutar(encargo, ventana)


def _cli(monkeypatch: pytest.MonkeyPatch, primero: str, final: str) -> None:
    motivo = ganchos.motivo("policy", ["aparece lo vetado"])

    def lanzar(orden: list[str], **opciones: Any) -> subprocess.CompletedProcess[str]:
        salida = _flujo(_entrega(primero), _entrega(final), bloqueo=motivo)
        return subprocess.CompletedProcess(orden, 0, stdout=salida, stderr="")

    monkeypatch.setattr(subprocess, "run", lanzar)


def test_el_que_insiste_detiene_la_obra_y_todo_queda_en_el_registro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un termino global, escrito con otra mayuscula, en todos los intentos: cada
    intento deja su vuelta y su fallo en el registro, la obra se detiene, la
    ficha dice por que y la API sirve el registro (RF-135 a RF-138)."""
    termino = sorted(t for t in TERMINOS_VETADOS_DE_SERIE if " " not in t)[0]
    escrito = termino.capitalize()
    _cli(monkeypatch, f"{escrito}, dijo.", f"Y otra vez: {escrito}.")
    app = crear_aplicacion(tmp_path / "api.sqlite3", ejecutor=RedactorDeVerdad())
    with TestClient(app) as cliente:
        id_obra = cliente.post("/obras", json=SIN_DESTINATARIO).json()["id_obra"]
        cliente.app.state.produccion.hilos[id_obra].join(timeout=60)  # type: ignore[attr-defined]
        ficha = cliente.get(f"/obras/{id_obra}").json()
        registro = cliente.get(f"/obras/{id_obra}/policy").json()
        fallidos = cliente.get(f"/obras/{id_obra}/policy?decision=intento_fallido").json()
        de_otro_nivel = cliente.get(f"/obras/{id_obra}/policy?nivel=tema_del_comprador")

    assert ficha["detenida"] is True
    assert escrito in ficha["motivo_de_la_detencion"]
    assert "redactar" in ficha["motivo_de_la_detencion"]

    reintentos = guion.paso(3).reintentos
    intentos = sorted({fila["intento"] for fila in registro})
    assert intentos == list(range(1, reintentos + 1))
    for intento in intentos:
        del_intento = [fila for fila in registro if fila["intento"] == intento]
        assert {fila["decision"] for fila in del_intento} == {
            "devuelto_al_agente",
            "intento_fallido",
        }
    assert all(fila["nivel"] == "global" and fila["termino"] == termino for fila in registro)
    assert all(fila["encontrado"] == escrito for fila in registro)
    assert all(fila["tarea"] == "redactar" and fila["capitulo"] == 1 for fila in registro)
    assert len(fallidos) == reintentos
    assert de_otro_nivel.json() == []


def test_lo_corregido_a_tiempo_queda_como_devuelto_y_la_obra_sigue(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli(monkeypatch, "Canto un búho en la torre.", "Canto un mochuelo en la torre.")
    id_obra = almacen.crear_obra(BRIEF)
    Caminante(almacen, RedactorDeVerdad(), catalogo=CatalogoFingido()).caminar_obra(  # type: ignore[arg-type]
        id_obra, 1
    )
    registro = almacen.listar_decisiones_de_policy(id_obra)
    assert registro, "la vuelta de la sesion tambien es una decision"
    assert {fila["decision"] for fila in registro} == {"devuelto_al_agente"}
    assert {(fila["nivel"], fila["encontrado"]) for fila in registro} == {
        ("palabra_del_comprador", "búho")
    }
    assert not almacen.esta_detenida(id_obra)
    assert almacen.motivo_de_la_detencion(id_obra) is None


def test_el_registro_es_de_solo_anadir(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli(monkeypatch, "Canto un búho.", "Canto un mochuelo.")
    id_obra = almacen.crear_obra(BRIEF)
    Caminante(almacen, RedactorDeVerdad(), catalogo=CatalogoFingido()).caminar_obra(  # type: ignore[arg-type]
        id_obra, 1
    )
    assert almacen.listar_decisiones_de_policy(id_obra)
    with pytest.raises(sqlite3.IntegrityError):
        almacen._escritor.execute("DELETE FROM decision_de_policy")
    with pytest.raises(sqlite3.IntegrityError):
        almacen._escritor.execute("UPDATE decision_de_policy SET termino = 'x'")


def test_sin_hooks_no_se_registra_nada(almacen: Almacen) -> None:
    """Un intento sin `ganchos` —el fingido de siempre— no deja filas."""
    id_obra = almacen.crear_obra(BRIEF)
    Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido()).caminar_obra(id_obra, 1)  # type: ignore[arg-type]
    assert almacen.listar_decisiones_de_policy(id_obra) == []
