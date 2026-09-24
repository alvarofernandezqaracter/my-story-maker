"""Los dos hooks de los subagentes de prosa (SPEC1 4.13, criterio 9 de §10).

Cierre por `prueba`, sin gastar: el hook es un programa y se le da la misma
entrada JSON que le daria Claude Code; la orden del ejecutor se mira sin
lanzarla; y el recorrido con un subagente fingido que insiste en lo vetado
termina en intento fallido, con el veredicto en la `Traza`. Que el CLI de verdad
dispara el hook en `--print` lo confirmaron los sondeos apuntados en el informe
de la tarea, no esta suite.
"""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from dobles import CatalogoFingido, EjecutorFingido
from novela import ganchos
from novela.ajustes import COSTE_FIJO_DEL_SUBAGENTE_EN_TOKENS, tokens_repartibles
from novela.almacen import Almacen
from novela.almacen.artefactos import abrir_almacen
from novela.ejecutor import (
    EjecutorDeSubagentes,
    SubagenteFallo,
    _tokens_de_entrada,
)
from novela.nucleo import guion, presupuesto
from novela.nucleo.caminante import Caminante, Resultado
from novela.nucleo.guion import Encargo, GuionInvalido
from novela.nucleo.proyecciones import Ventana
from novela.vocabularios import GANCHOS

VETO = "muerte de animales"

BRIEF = {
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
        "vetos": [VETO, "búho"],
    },
}


def _entrega(texto: str = "Ines cruzo la plaza con los pliegos.") -> str:
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


def _hook(
    gancho: str,
    texto: str,
    *,
    tarea: str = "redactar",
    vetos: list[str] | None = None,
    reserva: int = 4_000,
    ya_bloqueo: bool = False,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, str, str]:
    """Lo mismo que haria Claude Code: el entorno del ejecutor y la entrada JSON."""
    monkeypatch.setenv(ganchos.VARIABLE_DE_VETOS, json.dumps(vetos or []))
    monkeypatch.setenv(ganchos.VARIABLE_DE_RESERVA, str(reserva))
    entrada = json.dumps(
        {
            "hook_event_name": "Stop",
            "last_assistant_message": texto,
            "stop_hook_active": ya_bloqueo,
        }
    )
    return ganchos.principal([gancho, tarea], entrada)


# --- RF-120: que pasos los llevan ---------------------------------------------


def test_los_llevan_los_tres_pasos_de_prosa_y_ninguno_mas() -> None:
    con_ganchos = {paso.numero for paso in guion.PASOS if paso.ganchos}
    assert con_ganchos == {3, 5, 7}
    for paso in guion.PASOS:
        if paso.ganchos:
            assert set(paso.ganchos) == set(GANCHOS)
            assert paso.reserva_de_la_vuelta > 0
    assert not any(paso.ganchos for paso in guion.FUERA_DEL_GUION.values())


def test_las_cribas_del_mismo_rol_que_cose_no_los_llevan() -> None:
    encargos = guion.expandir(guion.paso(8), id_obra="obr_1", capitulo=1, escenas=("e1",))
    assert encargos and not any(encargo.ganchos for encargo in encargos)


@pytest.mark.parametrize(
    "roto",
    [
        {"ganchos": ["censura"], "reserva_de_la_vuelta": 4_000},
        {"ganchos": ["policy"]},
        {"ganchos": ["policy"], "reserva_de_la_vuelta": -1},
    ],
)
def test_un_hook_fuera_de_vocabulario_o_sin_reserva_no_carga(roto: dict[str, Any]) -> None:
    paso = {
        "numero": 3,
        "reintentos": 2,
        "al_agotarse": "detener_obra",
        "tarea": "redactar",
        "rol": "redactor",
        "concurrencia": "por_escena",
        "unidad": "escena",
        "proyeccion": [],
        **roto,
    }
    with pytest.raises(GuionInvalido):
        guion._a_paso(paso)


# --- RF-121 y RF-129: como viajan en la orden ------------------------------------


def _encargo_del_paso(numero: int) -> Encargo:
    return guion.expandir(guion.paso(numero), id_obra="obr_1", capitulo=1, escenas=("esc_1",))[
        0
    ]


def _ventana(vetos: tuple[str, ...] = ()) -> Ventana:
    return Ventana(materiales={}, texto="{}", tokens=1, vetos=vetos)


@pytest.mark.parametrize("numero", [3, 5, 7])
def test_la_orden_de_un_paso_de_prosa_lleva_los_dos_hooks_stop(numero: int) -> None:
    encargo = _encargo_del_paso(numero)
    orden = EjecutorDeSubagentes()._orden(encargo, _ventana())
    ajustes = json.loads(orden[orden.index("--settings") + 1])
    assert set(ajustes) == {"hooks"}, "solo hooks: nada mas de configuracion"
    assert set(ajustes["hooks"]) == {"Stop"}
    ordenes = [h["command"] for grupo in ajustes["hooks"]["Stop"] for h in grupo["hooks"]]
    for gancho in GANCHOS:
        assert any(
            f"-m novela.ganchos {gancho} {encargo.tarea}" in orden_del_hook
            for orden_del_hook in ordenes
        )
    # El aislamiento de 4.11 sigue igual.
    assert "--strict-mcp-config" in orden and "--no-session-persistence" in orden
    assert not any(parte.startswith("--mcp-config") for parte in orden)
    assert "--include-hook-events" in orden
    sistema = orden[orden.index("--system-prompt") + 1]
    assert "Stop hook feedback" in sistema and ganchos.PREFIJO in sistema


@pytest.mark.parametrize("numero", [1, 2, 4, 6, 8, 9, 10])
def test_la_orden_de_un_paso_sin_prosa_no_lleva_settings(numero: int) -> None:
    encargo = guion.expandir(
        guion.paso(numero), id_obra="obr_1", capitulo=1, escenas=("esc_1",)
    )[0]
    ejecutor = EjecutorDeSubagentes()
    orden = ejecutor._orden(encargo, _ventana())
    assert "--settings" not in orden
    assert "Stop hook feedback" not in orden[orden.index("--system-prompt") + 1]
    entorno = ejecutor._entorno(encargo, _ventana())
    assert ganchos.VARIABLE_DE_VETOS not in entorno
    assert ganchos.VARIABLE_DE_RESERVA not in entorno


def test_los_vetos_viajan_por_el_entorno_y_no_por_disco_ni_por_la_ventana() -> None:
    """D-46: el hook recibe la lista en el entorno del subagente. Nada va al
    directorio de la tarea, y el texto de la ventana no la lleva (RF-16)."""
    encargo = _encargo_del_paso(3)
    ventana = _ventana((VETO,))
    entorno = EjecutorDeSubagentes()._entorno(encargo, ventana)
    assert entorno is not None
    assert json.loads(entorno[ganchos.VARIABLE_DE_VETOS]) == [
        {"termino": VETO, "nivel": "tema_del_comprador"}
    ]
    assert entorno[ganchos.VARIABLE_DE_RESERVA] == str(encargo.reserva_de_la_vuelta)
    assert VETO not in EjecutorDeSubagentes()._encargo(ventana)


# --- RF-122 a RF-125: el programa del hook ----------------------------------


def test_una_entrega_buena_pasa_los_dos(monkeypatch: pytest.MonkeyPatch) -> None:
    for gancho in GANCHOS:
        codigo, _, error = _hook(gancho, _entrega(), vetos=[VETO], monkeypatch=monkeypatch)
        assert (codigo, error) == (ganchos.SALIDA_PASA, "")


def test_policy_bloquea_lo_vetado_y_lo_nombra(monkeypatch: pytest.MonkeyPatch) -> None:
    codigo, _, motivo = _hook(
        "policy",
        _entrega(f"Aquel invierno hubo {VETO} en la cuadra."),
        vetos=[VETO],
        monkeypatch=monkeypatch,
    )
    assert codigo == ganchos.SALIDA_BLOQUEA
    assert motivo.startswith(f"{ganchos.PREFIJO}policy]")
    assert VETO in motivo


def test_policy_compara_normalizado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Otra mayuscula casa igual (SPEC1 RF-132); el resto, en test_lo_vetado."""
    codigo, _, _ = _hook(
        "policy", _entrega("Hubo Muerte de animales."), vetos=[VETO], monkeypatch=monkeypatch
    )
    assert codigo == ganchos.SALIDA_BLOQUEA


def test_policy_sin_vetos_no_bloquea_nunca(monkeypatch: pytest.MonkeyPatch) -> None:
    codigo, _, _ = _hook("policy", _entrega(VETO), vetos=[], monkeypatch=monkeypatch)
    assert codigo == ganchos.SALIDA_PASA


@pytest.mark.parametrize(
    ("texto", "se_espera"),
    [
        ("pues mira, he pensado que...", "no devolvio JSON"),
        (json.dumps({"constancia": {}}), "`artefactos`"),
        (json.dumps({"artefactos": [{"tipo": "Parrafo", "cuerpo": {"texto": "x"}}]}), "falta"),
        (
            json.dumps(
                {
                    "artefactos": [
                        {
                            "tipo": "Borrador",
                            "cuerpo": {"texto": "", "unidad": "e", "cumple": []},
                        }
                    ]
                }
            ),
            "sin `texto`",
        ),
        (
            json.dumps({"artefactos": [{"tipo": "Borrador", "cuerpo": {"texto": "x"}}]}),
            "le faltan",
        ),
        (
            json.dumps(
                {
                    "artefactos": [
                        json.loads(_entrega())["artefactos"][0],
                        {"tipo": "Critica", "cuerpo": {"evidencia": "x"}},
                    ]
                }
            ),
            "`Critica` no es un tipo",
        ),
    ],
)
def test_validar_capitulo_bloquea_lo_malformado(
    texto: str, se_espera: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    codigo, _, motivo = _hook("validar_capitulo", texto, monkeypatch=monkeypatch)
    assert codigo == ganchos.SALIDA_BLOQUEA
    assert se_espera in motivo


def test_validar_capitulo_mira_el_esquema_de_su_tarea(monkeypatch: pytest.MonkeyPatch) -> None:
    """Revisar entrega una `Revision`: un `Borrador` solo no le basta."""
    codigo, _, motivo = _hook(
        "validar_capitulo", _entrega(), tarea="revisar", monkeypatch=monkeypatch
    )
    assert codigo == ganchos.SALIDA_BLOQUEA
    assert "`Revision`" in motivo


def test_se_pueden_sumar_comprobaciones_sin_tocar_el_enganche(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-48: la tarea de validadores programaticos anadira las suyas a la lista."""

    def sin_la_letra_z(
        entrega: dict[str, Any], tarea: str, datos: ganchos.DatosDeLaObra
    ) -> list[str]:
        return ["lleva z"] if "z" in json.dumps(entrega) else []

    ampliada = [*ganchos.COMPROBACIONES_DE_CAPITULO, sin_la_letra_z]
    monkeypatch.setattr(ganchos, "COMPROBACIONES_DE_CAPITULO", ampliada)
    codigo, _, motivo = _hook("validar_capitulo", _entrega("zas"), monkeypatch=monkeypatch)
    assert codigo == ganchos.SALIDA_BLOQUEA and "lleva z" in motivo


def test_una_vuelta_por_intento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si ya bloqueo alguien en este turno, termina: lo que quede lo juzga el
    ejecutor (RF-125)."""
    codigo, salida, _ = _hook(
        "policy", _entrega(VETO), vetos=[VETO], ya_bloqueo=True, monkeypatch=monkeypatch
    )
    assert codigo == ganchos.SALIDA_PASA
    assert "decide el ejecutor" in salida


def test_no_bloquea_si_la_vuelta_no_cabe_en_la_reserva(monkeypatch: pytest.MonkeyPatch) -> None:
    """RF-128: una respuesta enorme no se relee; el intento falla y el
    siguiente arranca en frio."""
    largo = "palabra " * 20_000 + VETO
    codigo, salida, _ = _hook(
        "policy", _entrega(largo), vetos=[VETO], reserva=4_000, monkeypatch=monkeypatch
    )
    assert codigo == ganchos.SALIDA_PASA
    assert "no cabe en la reserva" in salida
    assert ganchos.revisar("policy", "redactar", _entrega(largo), [VETO])


def test_el_motivo_esta_acotado(monkeypatch: pytest.MonkeyPatch) -> None:
    vetos = [f"palabra{numero}" for numero in range(300)]
    texto = _entrega(" ".join(vetos))
    codigo, _, motivo = _hook(
        "policy", texto, vetos=vetos, reserva=100_000, monkeypatch=monkeypatch
    )
    assert codigo == ganchos.SALIDA_BLOQUEA
    assert len(motivo) <= ganchos.TOPE_DEL_MOTIVO_EN_CARACTERES


def test_el_hook_es_un_proceso_que_sale_con_2_y_habla_en_utf8(tmp_path: Path) -> None:
    """El programa tal como lo lanza Claude Code: `python -m novela.ganchos`,
    con la entrada por stdin. Un veto con acento tiene que casar."""
    entorno = {
        **os.environ,
        ganchos.VARIABLE_DE_VETOS: json.dumps(["búho"]),
        ganchos.VARIABLE_DE_RESERVA: "4000",
    }
    entrada = json.dumps(
        {"last_assistant_message": _entrega("Canto un búho."), "stop_hook_active": False},
        ensure_ascii=False,
    ).encode("utf-8")
    terminado = subprocess.run(
        [sys.executable, "-m", "novela.ganchos", "policy", "redactar"],
        input=entrada,
        capture_output=True,
        env=entorno,
        cwd=tmp_path,
        timeout=60,
    )
    assert terminado.returncode == ganchos.SALIDA_BLOQUEA
    assert "búho" in terminado.stderr.decode("utf-8")
    assert list(tmp_path.iterdir()) == [], "el hook no escribe nada en disco"


# --- RF-126 a RF-128: lo que hace el ejecutor con lo que entregan -------------


def _flujo(texto_final: str, *, bloqueo: str | None = None) -> str:
    """Lo que devuelve `claude --print --output-format stream-json`."""
    lineas: list[dict[str, Any]] = [{"type": "system", "subtype": "init"}]
    if bloqueo is not None:
        lineas.append(
            {
                "type": "system",
                "subtype": "hook_response",
                "hook_event": "Stop",
                "exit_code": 2,
                "stdout": "",
                "stderr": bloqueo,
            }
        )
    for gancho in GANCHOS:
        lineas.append(
            {
                "type": "system",
                "subtype": "hook_response",
                "hook_event": "Stop",
                "exit_code": 0,
                "stdout": f"{ganchos.PREFIJO}{gancho}] pasa",
                "stderr": "",
            }
        )
    lineas.append(
        {
            "type": "result",
            "result": texto_final,
            "is_error": False,
            "usage": {
                "input_tokens": 3_000,
                "output_tokens": 50,
                "iterations": [{"input_tokens": 1_900, "output_tokens": 20}],
            },
        }
    )
    return "\n".join(json.dumps(linea, ensure_ascii=False) for linea in lineas)


def test_la_entrega_corregida_queda_con_su_veredicto() -> None:
    encargo = _encargo_del_paso(3)
    motivo = ganchos.motivo("policy", [f"aparece lo vetado: «{VETO}»"])
    resultado = EjecutorDeSubagentes()._recoger(
        encargo, _flujo(_entrega(), bloqueo=motivo), 10, (VETO,)
    )
    assert resultado.ganchos is not None
    assert [v["gancho"] for v in resultado.ganchos["en_sesion"] if v["bloquea"]] == ["policy"]
    assert all(final["pasa"] for final in resultado.ganchos["final"])
    assert {final["gancho"] for final in resultado.ganchos["final"]} == set(GANCHOS)


def test_lo_que_no_pasa_al_final_es_un_intento_fallido() -> None:
    encargo = _encargo_del_paso(3)
    with pytest.raises(SubagenteFallo) as fallo:
        EjecutorDeSubagentes()._recoger(encargo, _flujo(_entrega(VETO)), 10, (VETO,))
    assert fallo.value.ganchos is not None
    policy = next(f for f in fallo.value.ganchos["final"] if f["gancho"] == "policy")
    assert not policy["pasa"] and VETO in policy["motivos"][0]


def test_la_entrada_medida_es_la_de_la_ultima_llamada() -> None:
    """`usage` suma las dos llamadas de una vuelta; el techo es de lo abierto a
    la vez, y la ultima llamada es la mayor (RF-128)."""
    envoltorio = json.loads(_flujo(_entrega()).splitlines()[-1])
    assert _tokens_de_entrada(envoltorio) == 1_900


def test_la_tanda_de_un_paso_con_hooks_reserva_su_vuelta() -> None:
    encargo = _encargo_del_paso(3)
    sin_ganchos = Encargo(**{**encargo.__dict__, "ganchos": ()})
    abierto = encargo.tope_de_ventana + COSTE_FIJO_DEL_SUBAGENTE_EN_TOKENS
    esperada = tokens_repartibles() // (abierto + encargo.reserva_de_la_vuelta)
    anchura = presupuesto.anchura_de_tanda([encargo])
    assert anchura == esperada
    assert anchura <= presupuesto.anchura_de_tanda([sin_ganchos])


# --- Criterio 9: el recorrido con un Redactor que insiste en lo vetado --------


@dataclass
class RedactorQueInsiste:
    """El fingido de siempre, salvo `redactar`, que pasa por el ejecutor real
    con el CLI interceptado: su texto trae lo vetado en todos los intentos."""

    interno: EjecutorFingido = field(default_factory=EjecutorFingido)
    real: EjecutorDeSubagentes = field(default_factory=EjecutorDeSubagentes)
    entornos: list[dict[str, str] | None] = field(default_factory=list)
    ventanas: list[Ventana] = field(default_factory=list)

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        if encargo.tarea != "redactar":
            return self.interno.ejecutar(encargo, ventana)
        self.ventanas.append(ventana)
        return self.real.ejecutar(encargo, ventana)


@pytest.fixture
def almacen(tmp_path: Path) -> Iterator[Almacen]:
    almacen = abrir_almacen(tmp_path / "ganchos.sqlite3")
    yield almacen
    almacen.cerrar()


def test_un_redactor_que_insiste_en_lo_vetado_detiene_la_obra(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    ejecutor = RedactorQueInsiste()
    motivo = ganchos.motivo("policy", [f"aparece lo vetado: «{VETO}»"])

    def lanzar(orden: list[str], **opciones: Any) -> subprocess.CompletedProcess[str]:
        ejecutor.entornos.append(opciones.get("env"))
        salida = _flujo(_entrega(f"Y hubo {VETO}."), bloqueo=motivo)
        return subprocess.CompletedProcess(orden, 0, stdout=salida, stderr="")

    monkeypatch.setattr(subprocess, "run", lanzar)
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())  # type: ignore[arg-type]
    caminante.caminar_obra(id_obra, 1)

    assert almacen.esta_detenida(id_obra)
    assert almacen.listar("Borrador", id_obra) == [], "lo vetado no llega al almacen"
    paso = guion.paso(3)
    trazas = almacen.listar_trazas(id_obra, tarea="redactar")
    assert [t.propias["intento"] for t in trazas] == list(range(1, paso.reintentos + 1))
    for traza in trazas:
        registro = traza.cuerpo["ganchos"]
        assert any(v["bloquea"] for v in registro["en_sesion"])
        policy = next(f for f in registro["final"] if f["gancho"] == "policy")
        assert not policy["pasa"]
    # Los vetos del brief llegaron al hook por el entorno y no a la ventana.
    entorno = ejecutor.entornos[0]
    assert entorno is not None
    assert VETO in [v["termino"] for v in json.loads(entorno[ganchos.VARIABLE_DE_VETOS])]
    assert all(VETO not in ventana.texto for ventana in ejecutor.ventanas)


def test_la_api_sirve_el_veredicto_de_los_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RI-15: la `Traza` servida trae `ganchos`, y vacio en un paso sin hooks."""
    from fastapi.testclient import TestClient

    from novela.api.aplicacion import crear_aplicacion

    def lanzar(orden: list[str], **opciones: Any) -> subprocess.CompletedProcess[str]:
        salida = _flujo(_entrega(f"Y hubo {VETO}."))
        return subprocess.CompletedProcess(orden, 0, stdout=salida, stderr="")

    monkeypatch.setattr(subprocess, "run", lanzar)
    app = crear_aplicacion(tmp_path / "api.sqlite3", ejecutor=RedactorQueInsiste())
    with TestClient(app) as cliente:
        id_obra = cliente.post("/obras", json=BRIEF).json()["id_obra"]
        hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
        hilo.join(timeout=60)
        de_redactar = cliente.get(f"/obras/{id_obra}/trazas?tarea=redactar").json()
        de_planificar = cliente.get(f"/obras/{id_obra}/trazas?tarea=planificar").json()

    assert de_redactar and all(t["ganchos"]["final"] for t in de_redactar)
    policy = next(f for f in de_redactar[0]["ganchos"]["final"] if f["gancho"] == "policy")
    assert policy["pasa"] is False
    assert de_planificar and all(t["ganchos"] is None for t in de_planificar)
