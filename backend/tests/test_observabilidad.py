"""La produccion, observada en Langfuse (SPEC1 4.20, RF-183 a RF-192).

Metodo: `prueba`. Evidencia citable: lo que un Langfuse fingido recibe mientras
una obra entera corre con el ejecutor fingido —trazas, observaciones, scores y
prompts—, cotejado con lo que el almacen guardo. Ninguna prueba toca la red: la
del SDK de verdad exporta a memoria.
"""

import contextlib
import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dobles import EjecutorFingido
from novela import ganchos, observabilidad
from novela.api.aplicacion import crear_aplicacion
from novela.ejecutor import EjecutorDeSubagentes, SubagenteFallo
from novela.nucleo import guion
from novela.nucleo.caminante import Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana
from novela.observabilidad import (
    Observabilidad,
    PromptVersionado,
    id_de_score_de_la_puerta,
    id_de_traza,
    id_de_traza_de_entrevista,
)
from novela.tareas import prompt_de_tarea, tareas_declaradas
from novela.vocabularios import VALIDADOR_DE_LA_PUERTA

# --- El Langfuse fingido -------------------------------------------------------


@dataclass
class ObservacionFingida:
    id: str
    traza: str
    padre: str | None
    nombre: str
    tipo: str
    sesion: str
    nombre_de_traza: str
    campos: dict[str, Any]
    cambios: dict[str, Any] = field(default_factory=dict)
    cerrada: bool = False

    def update(self, **campos: Any) -> None:
        self.cambios.update(campos)

    def end(self) -> None:
        self.cerrada = True

    def todo(self) -> dict[str, Any]:
        return self.campos | self.cambios


@dataclass
class LangfuseFingido:
    """Guarda lo que se le manda. Con `falla`, todo lo que se le pide revienta."""

    falla: bool = False
    observaciones: list[ObservacionFingida] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)
    prompts: dict[str, list[str]] = field(default_factory=dict)
    consultas_de_prompt: list[str] = field(default_factory=list)

    def _quizas_fallar(self) -> None:
        if self.falla:
            raise ConnectionError("Langfuse no contesta")

    def abrir(self, **datos: Any) -> ObservacionFingida:
        self._quizas_fallar()
        observacion = ObservacionFingida(id=f"obs{len(self.observaciones)}", **datos)
        self.observaciones.append(observacion)
        return observacion

    def score(self, **campos: Any) -> None:
        self._quizas_fallar()
        self.scores.append(campos)

    def prompt(self, nombre: str) -> PromptVersionado | None:
        self.consultas_de_prompt.append(nombre)
        self._quizas_fallar()
        versiones = self.prompts.get(nombre)
        if not versiones:
            return None
        return PromptVersionado(versiones[-1], len(versiones), del_sdk=(nombre, len(versiones)))

    def crear_prompt(self, nombre: str, texto: str) -> PromptVersionado:
        self._quizas_fallar()
        self.prompts.setdefault(nombre, []).append(texto)
        version = len(self.prompts[nombre])
        return PromptVersionado(texto, version, del_sdk=(nombre, version))

    def vaciar(self) -> None:
        self._quizas_fallar()

    def de_la_traza(self, traza: str) -> list[ObservacionFingida]:
        return [o for o in self.observaciones if o.traza == traza]


# --- Una obra entera, observada ----------------------------------------------

BORRADOR = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "capitulos_objetivo": 2,
}

PROSA = "Version cosida de la escena. " + "tinta " * 400


@dataclass
class EjecutorQueMide:
    """El fingido de siempre, con lo que el CLI de verdad devuelve de medida y
    una llamada a herramienta en cada `documentar`."""

    interno: EjecutorFingido = field(
        default_factory=lambda: EjecutorFingido(texto_cosido=PROSA)
    )

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        resultado = self.interno.ejecutar(encargo, ventana)
        resultado.tokens_de_entrada_medidos = 1_000
        resultado.tokens_de_salida = 200
        resultado.coste = 0.01
        resultado.latencia_ms = 50
        resultado.modelo = "claude-haiku-fingido"
        if encargo.tarea == "documentar":
            resultado.herramientas = [
                {"nombre": "WebSearch", "entrada": "Sevilla 1587", "salida": "...",
                 "error": False}
            ]
        return resultado


class DemostradorQueDemuestra:
    def comprobar(self, sucesos: Any) -> dict[str, Any]:
        return {"comprobacion": "demostrada", "fallos": []}


@contextmanager
def _cliente(tmp_path: Path, langfuse: LangfuseFingido) -> Iterator[TestClient]:
    app = crear_aplicacion(
        tmp_path / "observada.sqlite3",
        ejecutor=EjecutorQueMide(),
        demostrador=DemostradorQueDemuestra(),
        observabilidad=Observabilidad(langfuse),
    )
    with TestClient(app) as cliente:
        yield cliente
        casa = cliente.app.state.produccion  # type: ignore[attr-defined]
        for hilo in [*casa.hilos.values(), casa.hilo_de_los_prompts]:
            if hilo is not None:
                hilo.join(timeout=120)


def _esperar(cliente: TestClient, id_obra: str) -> None:
    hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
    hilo.join(timeout=120)
    assert not hilo.is_alive(), "la produccion no termino"


def _obra_desde_una_entrevista(cliente: TestClient) -> tuple[str, str]:
    respuesta = cliente.post("/entrevistas", json={"borrador": BORRADOR, "textos": []})
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["id_obra"], cuerpo
    _esperar(cliente, cuerpo["id_obra"])
    return cuerpo["id_entrevista"], cuerpo["id_obra"]


@pytest.fixture
def langfuse() -> LangfuseFingido:
    return LangfuseFingido()


def test_una_novela_es_una_sesion_con_la_traza_de_la_entrevista_y_la_de_cada_version(
    tmp_path: Path, langfuse: LangfuseFingido
) -> None:
    """RF-184: la sesion nace con la entrevista y la obra la hereda; rehacer abre
    la traza de la version 2 en la misma sesion."""
    with _cliente(tmp_path, langfuse) as cliente:
        id_entrevista, id_obra = _obra_desde_una_entrevista(cliente)
        rehecha = cliente.post(f"/obras/{id_obra}/versiones", json={"desde_capitulo": 2})
        assert rehecha.status_code == 202
        _esperar(cliente, id_obra)

    de_la_entrevista = langfuse.de_la_traza(id_de_traza_de_entrevista(id_entrevista))
    assert [o.nombre for o in de_la_entrevista] == ["entrevistador · entrevistar"]
    v1 = langfuse.de_la_traza(id_de_traza(id_obra, 1))
    v2 = langfuse.de_la_traza(id_de_traza(id_obra, 2))
    assert v1 and v2
    trazas = {o.traza for o in langfuse.observaciones}
    assert trazas == {
        id_de_traza_de_entrevista(id_entrevista),
        id_de_traza(id_obra, 1),
        id_de_traza(id_obra, 2),
    }
    assert {o.sesion for o in langfuse.observaciones} == {id_entrevista}
    assert {o.nombre_de_traza for o in v1} == {f"{BORRADOR['titulo']} · v1"}
    # La 2 solo reescribe el capitulo 2: el 1 lo comparte y no se vuelve a observar.
    assert {o.nombre for o in v2 if o.tipo == "span"} == {"capitulo 2"}


def test_un_span_por_capitulo_y_una_generacion_por_intento_con_su_medida(
    tmp_path: Path, langfuse: LangfuseFingido
) -> None:
    """RF-185, RF-186 y OBJ-09: cada `Traza` es una generacion `<rol> · <tarea>`
    con sus tokens, su coste y su latencia; cuelga de su capitulo y el capitulo
    lleva la suma de lo suyo."""
    with _cliente(tmp_path, langfuse) as cliente:
        _, id_obra = _obra_desde_una_entrevista(cliente)
        casa = cliente.app.state.produccion  # type: ignore[attr-defined]
        trazas = casa.almacen.listar_trazas(id_obra)
        # La auditoria de cierre lleva el capitulo 2 pero corre cuando ya ha
        # cerrado: su coste es de la version, no del capitulo.
        del_capitulo = {
            n: [t for t in trazas if t.capitulo == n and t.propias.get("tarea") != "auditar"]
            for n in (1, 2)
        }

    observadas = langfuse.de_la_traza(id_de_traza(id_obra, 1))
    generaciones = [o for o in observadas if o.tipo == "generation"]
    capitulos = {o.nombre: o for o in observadas if o.tipo == "span"}

    assert len(generaciones) == len(trazas), "OBJ-09: toda Traza tiene su generacion"
    assert {g.campos["metadata"]["id_traza"] for g in generaciones} == {t.id for t in trazas}
    assert set(capitulos) == {"capitulo 1", "capitulo 2"}
    assert all(o.cerrada for o in observadas), "todo se cierra: sin cerrar, no se manda"
    for generacion in generaciones:
        todo = generacion.todo()
        datos = generacion.campos["metadata"]
        assert generacion.nombre == f"{datos['rol']} · {datos['tarea']}"
        assert todo["metadata"]["latencia_ms"] == 50
        assert todo["usage_details"] == {"input": 1_000, "output": 200}
        assert todo["cost_details"] == {"total": 0.01}
        assert todo["model"] == "claude-haiku-fingido"
        capitulo = datos["capitulo"]
        if datos["tarea"] in {"poblar_mundo", "auditar"}:
            assert generacion.padre is None, "fuera de todo capitulo"
        else:
            assert generacion.padre == capitulos[f"capitulo {capitulo}"].id
    for numero in (1, 2):
        totales = capitulos[f"capitulo {numero}"].todo()["metadata"]["totales"]
        assert totales["tareas"] == len(del_capitulo[numero])
        assert totales["coste"] == pytest.approx(0.01 * len(del_capitulo[numero]))
        assert totales["tokens_de_entrada"] == 1_000 * len(del_capitulo[numero])


def test_cada_llamada_a_herramienta_es_una_observacion_hija(
    tmp_path: Path, langfuse: LangfuseFingido
) -> None:
    """RF-185: `herramienta · <nombre>`, colgando de la generacion que la hizo."""
    with _cliente(tmp_path, langfuse) as cliente:
        _, id_obra = _obra_desde_una_entrevista(cliente)

    por_id = {o.id: o for o in langfuse.observaciones}
    herramientas = [o for o in langfuse.observaciones if o.tipo == "tool"]
    assert herramientas
    for herramienta in herramientas:
        assert herramienta.nombre == "herramienta · WebSearch"
        assert herramienta.campos["input"] == "Sevilla 1587"
        assert por_id[herramienta.padre or ""].nombre == "documentalista · documentar"


def test_la_version_terminada_lleva_los_totales_de_la_version_y_de_la_novela(
    tmp_path: Path, langfuse: LangfuseFingido
) -> None:
    """RF-186: la novela entera suma sus versiones y las pasadas de su entrevista."""
    with _cliente(tmp_path, langfuse) as cliente:
        id_entrevista, id_obra = _obra_desde_una_entrevista(cliente)
        almacen = cliente.app.state.produccion.almacen  # type: ignore[attr-defined]
        de_la_version = almacen.sumar_trazas(id_obra, version=1)
        de_la_entrevista = almacen.sumar_pasadas(id_entrevista)

    [evento] = [o for o in langfuse.observaciones if o.nombre == "version terminada"]
    totales = evento.campos["metadata"]
    assert totales["totales_de_la_version"] == de_la_version
    novela = totales["totales_de_la_novela"]
    assert novela["tareas"] == de_la_version["tareas"] + de_la_entrevista["tareas"]
    assert novela["coste"] == pytest.approx(de_la_version["coste"] + de_la_entrevista["coste"])


def test_los_prompts_de_todas_las_tareas_se_versionan_y_cada_generacion_se_enlaza(
    tmp_path: Path, langfuse: LangfuseFingido
) -> None:
    """RF-188: las tareas se leen de `tareas/`, no se suponen; el texto es el del
    repositorio y cada generacion lleva la version del prompt de su tarea."""
    with _cliente(tmp_path, langfuse) as cliente:
        _obra_desde_una_entrevista(cliente)

    assert set(langfuse.prompts) == set(tareas_declaradas())
    for tarea, versiones in langfuse.prompts.items():
        assert versiones == [prompt_de_tarea(tarea)], "una sola version: el texto no cambio"
    for generacion in (o for o in langfuse.observaciones if o.tipo == "generation"):
        tarea = generacion.nombre.split(" · ")[1]
        assert generacion.cambios["prompt"] == (tarea, 1)


def test_un_prompt_se_sube_solo_si_su_texto_cambio() -> None:
    """RF-188, D-81: reiniciar no inventa versiones; cambiar el texto, si."""
    langfuse = LangfuseFingido(prompts={"redactar": ["texto viejo"]})
    textos = {"redactar": "texto viejo", "revisar": "texto de revisar"}
    Observabilidad(langfuse, leer_prompt=textos.__getitem__).registrar_prompts(textos)
    assert langfuse.prompts == {"redactar": ["texto viejo"], "revisar": ["texto de revisar"]}

    textos["redactar"] = "texto nuevo"
    otra = Observabilidad(langfuse, leer_prompt=textos.__getitem__)
    assert otra.registrar_prompts(["redactar", "redactar"]) == {"redactar": 2}
    assert langfuse.prompts["redactar"] == ["texto viejo", "texto nuevo"]
    assert langfuse.consultas_de_prompt.count("redactar") == 2, "una vez por proceso"


def test_la_puerta_deja_un_score_por_validador_que_se_sustituye_al_repetirla(
    tmp_path: Path, langfuse: LangfuseFingido
) -> None:
    """RF-187: 1 sin fallos, 0 con ellos; el `id` sale de obra, version y validador."""
    with _cliente(tmp_path, langfuse) as cliente:
        _, id_obra = _obra_desde_una_entrevista(cliente)
        primera = cliente.get(f"/obras/{id_obra}/versiones/1/puerta").json()
        cliente.get(f"/obras/{id_obra}/versiones/1/puerta")

    de_la_puerta = [s for s in langfuse.scores if s["name"].startswith("puerta.")]
    assert {s["name"] for s in de_la_puerta} == {f"puerta.{v}" for v in VALIDADOR_DE_LA_PUERTA}
    assert all(s["trace_id"] == id_de_traza(id_obra, 1) for s in de_la_puerta)
    assert {s["score_id"] for s in de_la_puerta} == {
        id_de_score_de_la_puerta(id_obra, 1, v) for v in VALIDADOR_DE_LA_PUERTA
    }, "volver a pasarla repite los mismos ids: Langfuse sustituye"
    fallan = {f["validador"] for f in primera["fallos"]}
    for score in de_la_puerta:
        validador = score["name"].removeprefix("puerta.")
        assert score["value"] == (0.0 if validador in fallan else 1.0)


def test_sin_comprobacion_formal_no_hay_score_de_cronologia() -> None:
    langfuse = LangfuseFingido()
    Observabilidad(langfuse).resultado_de_la_puerta(
        "obr_1", 1,
        [{"validador": "longitud", "capitulo": 2, "detalle": "el capitulo es corto"}],
        "sin_comprobacion",
    )
    nombres = {s["name"]: s for s in langfuse.scores}
    assert "puerta.cronologia" not in nombres
    assert nombres["puerta.longitud"]["value"] == 0.0
    assert "capitulo 2" in nombres["puerta.longitud"]["comment"]
    assert nombres["puerta.nombres"]["value"] == 1.0


def test_cada_hook_deja_su_veredicto_como_score_de_su_generacion() -> None:
    """RF-187: `gancho.<hook>` con el veredicto final del ejecutor."""
    langfuse = LangfuseFingido()
    vista = Observabilidad(langfuse)
    vista.abrir_tarea("trz_1", id_obra="obr_1", version=1, rol="redactor", tarea="redactar",
                      intento=1, capitulo=1)
    vista.cerrar_tarea("trz_1", ganchos={"en_sesion": [], "final": [
        {"gancho": "validar_capitulo", "pasa": True, "motivos": []},
        {"gancho": "policy", "pasa": False, "motivos": ["aparece «joder»"]},
    ]}, error="no pasa policy")

    [generacion] = langfuse.observaciones
    assert generacion.cambios["level"] == "ERROR"
    scores = {s["name"]: s for s in langfuse.scores}
    assert scores["gancho.validar_capitulo"]["value"] == 1.0
    assert scores["gancho.policy"]["value"] == 0.0
    assert scores["gancho.policy"]["observation_id"] == generacion.id
    assert scores["gancho.policy"]["comment"] == "aparece «joder»"


# --- RF-189. Lo que otras piezas usan ------------------------------------------


def test_obtener_prompt_y_enviar_score_usan_la_del_proceso() -> None:
    langfuse = LangfuseFingido(prompts={"juez": ["uno", "dos"]})
    anterior = observabilidad.instalar(Observabilidad(langfuse))
    try:
        prompt = observabilidad.obtener_prompt("juez")
        assert prompt is not None and (prompt.texto, prompt.version) == ("dos", 2)
        assert observabilidad.obtener_prompt("no_existe") is None
        observabilidad.enviar_score("obr_1", 3, "juez.ritmo", 0.7, "bien")
    finally:
        observabilidad.instalar(anterior)
    assert langfuse.scores == [{
        "name": "juez.ritmo", "value": 0.7, "trace_id": id_de_traza("obr_1", 3),
        "data_type": "NUMERIC", "comment": "bien",
    }]


def test_apagada_no_hace_nada_y_lo_dice() -> None:
    apagada = Observabilidad()
    assert not apagada.activa
    assert apagada.obtener_prompt("redactar") is None
    assert apagada.enviar_score("obr_1", 1, "x", 1.0, "") is None
    assert observabilidad.obtener_prompt("redactar") is None, "la bateria va apagada (RF-192)"


# --- RF-183. Las claves ----------------------------------------------------------


def test_las_claves_salen_del_entorno_y_lo_que_falta_del_env(tmp_path: Path) -> None:
    fichero = tmp_path / ".env"
    fichero.write_text(
        "# claves de prueba\nLANGFUSE_PUBLIC_KEY=pk-del-fichero\n"
        "LANGFUSE_SECRET_KEY='sk-del-fichero'\n",
        encoding="utf-8",
    )
    assert observabilidad.claves({}, fichero) == {
        "public_key": "pk-del-fichero", "secret_key": "sk-del-fichero",
        "base_url": "https://cloud.langfuse.com",
    }
    entorno = {"LANGFUSE_PUBLIC_KEY": "pk-del-entorno", "LANGFUSE_HOST": "https://otro"}
    assert observabilidad.claves(entorno, fichero) == {
        "public_key": "pk-del-entorno", "secret_key": "sk-del-fichero",
        "base_url": "https://otro",
    }
    assert observabilidad.claves({"LANGFUSE_PUBLIC_KEY": "pk"}, tmp_path / "no-hay") is None


def test_sin_claves_no_hay_cliente_y_el_env_no_se_copia_al_entorno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in list(os.environ):
        if variable.startswith("LANGFUSE_"):
            monkeypatch.delenv(variable)
    monkeypatch.setattr(observabilidad, "FICHERO_DE_CLAVES", tmp_path / "no-hay")
    assert not observabilidad.desde_el_entorno().activa

    fichero = tmp_path / ".env"
    fichero.write_text("LANGFUSE_PUBLIC_KEY=pk-lf-prueba\nLANGFUSE_SECRET_KEY=sk-lf-prueba\n")
    monkeypatch.setattr(observabilidad, "FICHERO_DE_CLAVES", fichero)
    creados: list[dict[str, str]] = []

    class ClienteQueApunta:
        def __init__(self, **configuracion: str) -> None:
            creados.append(configuracion)

    monkeypatch.setattr(observabilidad, "ClienteLangfuse", ClienteQueApunta)
    assert observabilidad.desde_el_entorno().activa
    assert creados[0]["public_key"] == "pk-lf-prueba"
    assert "LANGFUSE_PUBLIC_KEY" not in os.environ, "se lee, no se exporta (D-79)"


# --- RF-190 y RNF-10. La observacion nunca para la novela ------------------------


def test_con_langfuse_roto_la_novela_termina_igual(tmp_path: Path) -> None:
    """Todo lo que se pide a Langfuse revienta, y la obra escribe lo mismo que
    con Langfuse apagado: mismas trazas, mismo manuscrito."""

    def producir(carpeta: Path, observacion: Observabilidad) -> dict[str, Any]:
        carpeta.mkdir()
        app = crear_aplicacion(
            carpeta / "obra.sqlite3",
            ejecutor=EjecutorQueMide(),
            demostrador=DemostradorQueDemuestra(),
            observabilidad=observacion,
        )
        with TestClient(app) as cliente:
            _, id_obra = _obra_desde_una_entrevista(cliente)
            publicar = cliente.post(f"/obras/{id_obra}/versiones/1/publicar")
            trazas = cliente.get(f"/obras/{id_obra}/trazas").json()
            return {
                "recorrido": [
                    (t["rol"], t["tarea"], t["capitulo"], t["intento"]) for t in trazas
                ],
                "manuscrito": [
                    u["texto"]
                    for u in cliente.get(f"/obras/{id_obra}/manuscrito").json()["unidades"]
                ],
                "publicar": publicar.status_code,
            }

    roto = LangfuseFingido(falla=True)
    con_langfuse_roto = producir(tmp_path / "rota", Observabilidad(roto))
    sin_langfuse = producir(tmp_path / "apagada", Observabilidad())

    assert con_langfuse_roto == sin_langfuse
    assert roto.observaciones == [] and roto.scores == []
    # El prompt que falla se recuerda: una consulta por tarea y proceso, no por intento.
    assert len(roto.consultas_de_prompt) == len(set(roto.consultas_de_prompt))


# --- RF-191. El subagente no ve Langfuse ----------------------------------------


def _encargo(numero: int) -> Encargo:
    paso = guion.paso(numero)
    return guion.expandir(paso, id_obra="obr_1", capitulo=1, escenas=("esc_1",))[0]


@pytest.mark.parametrize("numero", [2, 3], ids=["sin hooks", "con hooks"])
def test_ningun_subagente_hereda_una_variable_de_langfuse(
    numero: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba")
    monkeypatch.setenv("langfuse_host", "https://prueba")
    entornos: list[dict[str, str]] = []

    def lanzar(orden: list[str], **opciones: Any) -> subprocess.CompletedProcess[str]:
        entornos.append(opciones["env"])
        salida = json.dumps({"result": '{"artefactos": []}', "usage": {}})
        return subprocess.CompletedProcess(orden, 0, stdout=salida, stderr="")

    monkeypatch.setattr(subprocess, "run", lanzar)
    encargo = _encargo(numero)
    # Lo que devuelve no importa aqui: con hooks, un `Borrador` que falta es un
    # intento fallido, pero el subagente ya se lanzo con su entorno.
    with contextlib.suppress(SubagenteFallo):
        EjecutorDeSubagentes().ejecutar(encargo, Ventana(materiales={}, texto="", tokens=0))

    [entorno] = entornos
    assert entorno is not None, "el entorno se pasa siempre, filtrado"
    assert not [clave for clave in entorno if clave.upper().startswith("LANGFUSE_")]
    assert "PATH" in {clave.upper() for clave in entorno}, "lo demas se hereda"
    assert (ganchos.VARIABLE_DE_VETOS in entorno) == bool(encargo.ganchos)


def test_el_ejecutor_lee_las_llamadas_a_herramienta_del_flujo_del_cli() -> None:
    """RF-185: cada `tool_use` con su `tool_result`, del `stream-json`."""
    flujo = "\n".join(json.dumps(linea) for linea in [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "WebSearch", "input": {"query": "1587"}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "Sevilla",
             "is_error": False},
        ]}},
        {"type": "result", "result": '{"artefactos": []}', "usage": {"output_tokens": 3},
         "total_cost_usd": 0.002},
    ])
    ejecutor = EjecutorDeSubagentes()
    resultado = ejecutor._recoger(_encargo(2), flujo, 10)
    assert resultado.herramientas == [
        {"nombre": "WebSearch", "entrada": '{"query": "1587"}', "salida": "Sevilla",
         "error": False}
    ]
    assert resultado.modelo == ejecutor.modelo


# --- El SDK de verdad, sin red ----------------------------------------------------


def test_el_sdk_de_verdad_recibe_la_sesion_la_traza_y_el_padre() -> None:
    """Lo que `ClienteLangfuse` abre es lo que Langfuse espera: el `id` de traza
    es el de la semilla del SDK, la sesion va en cada observacion y el hijo
    cuelga de su padre. Exporta a memoria: no toca la red."""
    pytest.importorskip("langfuse")
    from langfuse import Langfuse
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exportado = InMemorySpanExporter()
    cliente = observabilidad.ClienteLangfuse(
        public_key="pk-lf-prueba", secret_key="sk-lf-prueba",
        base_url="http://127.0.0.1:9", span_exporter=exportado,
    )
    vista = Observabilidad(cliente)
    vista.abrir_capitulo("obr_1", 1, 1, id_entrevista="ent_1", titulo="Obra")
    vista.abrir_tarea("trz_1", id_obra="obr_1", version=1, rol="redactor", tarea="redactar",
                      intento=1, capitulo=1, id_entrevista="ent_1", titulo="Obra")
    vista.cerrar_tarea("trz_1", tokens_de_entrada=10, tokens_de_salida=5, coste=0.01,
                       herramientas=[{"nombre": "WebSearch", "entrada": "x"}])
    vista.cerrar_capitulo("obr_1", 1, 1, {"coste": 0.01})
    cliente._sdk.flush()

    spans = {span.name: span for span in exportado.get_finished_spans()}
    assert set(spans) == {"capitulo 1", "redactor · redactar", "herramienta · WebSearch"}
    traza = Langfuse.create_trace_id(seed="obra:obr_1:version:1")
    assert traza == id_de_traza("obr_1", 1)
    for span in spans.values():
        assert format(span.context.trace_id, "032x") == traza
        assert span.attributes is not None and span.attributes["session.id"] == "ent_1"
    padre = spans["redactor · redactar"].parent
    assert padre is not None and padre.span_id == spans["capitulo 1"].context.span_id
