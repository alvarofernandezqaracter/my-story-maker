"""La produccion, observada en Langfuse (SPEC1 4.20).

Si hay claves, lo que el sistema ya mide —tokens, coste, latencia, lo que
dijeron los hooks, el resultado de la puerta— se manda tambien a Langfuse: una
**sesion por novela**, una traza por la entrevista y otra por cada version de la
obra, un span por capitulo, una generacion por intento de tarea con un hijo por
llamada a herramienta, los validadores como scores y los prompts de las tareas
versionados solos. Sin claves no se manda nada y nada cambia.

Tres reglas sostienen el modulo:

- **Es un espejo de salida.** Nada de la produccion lee de aqui (D-82): el
  estado sigue en SQLite, y aqui no se abre el almacen. Quien llama pasa lo ya
  leido, igual que al demostrador.
- **Nunca para la novela** (RF-190). Todo lo publico se traga sus fallos y los
  anota en el registro del proceso. Lo que se manda va por la cola en segundo
  plano del SDK; lo unico que espera a la red es consultar y crear la version
  de un prompt, con tope y una sola vez por prompt y proceso.
- **Nada se guarda** (RD-31). La traza de cada version y el `id` de cada score
  de la puerta se derivan de la obra y la version con la semilla del SDK: una
  caida y un relanzamiento caen en la misma traza sin escribir nada.

Las claves salen del entorno y, lo que falte ahi, del `.env` de la raiz del
repositorio, que se lee y **no se copia al entorno del proceso** (D-79). Aun
asi, el ejecutor quita toda variable `LANGFUSE_` del entorno de cada subagente
(RF-191): un rol no puede ver como se le juzga.
"""

import functools
import hashlib
import logging
import os
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from novela.vocabularios import VALIDADOR_DE_LA_PUERTA

# src/novela/observabilidad.py -> la raiz del repositorio esta tres carpetas arriba.
RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parents[3]
FICHERO_DE_CLAVES = RAIZ_DEL_REPOSITORIO / ".env"

PREFIJO_DE_LAS_VARIABLES = "LANGFUSE_"
VARIABLE_DE_LA_CLAVE_PUBLICA = "LANGFUSE_PUBLIC_KEY"
VARIABLE_DE_LA_CLAVE_SECRETA = "LANGFUSE_SECRET_KEY"
VARIABLE_DEL_HOST = "LANGFUSE_HOST"
HOST_POR_DEFECTO = "https://cloud.langfuse.com"

# Lo unico que espera a la red: la version de un prompt (RF-190).
ESPERA_DE_LOS_PROMPTS_EN_SEGUNDOS = 5
# La etiqueta con la que se sube cada version nueva: la ultima es la que vale.
ETIQUETA_DE_LOS_PROMPTS = "production"
# Lo que se manda de cada llamada a herramienta y de cada comentario se recorta:
# es para reconocerlo, no una copia del almacen.
TOPE_DE_LO_QUE_SE_MANDA_EN_CARACTERES = 2_000
TOPE_DEL_COMENTARIO_EN_CARACTERES = 1_000

registro = logging.getLogger("novela.observabilidad")


# --- Las claves --------------------------------------------------------------


def leer_dotenv(ruta: Path) -> dict[str, str]:
    """`CLAVE=valor` por linea, con comentarios y comillas. Si no existe, nada."""
    try:
        texto = ruta.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    valores: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        elif " #" in valor:
            valor = valor.split(" #", 1)[0].rstrip()
        if clave:
            valores[clave] = valor
    return valores


def claves(
    entorno: Mapping[str, str] | None = None, fichero: Path | None = None
) -> dict[str, str] | None:
    """Las claves de Langfuse, o nada si falta alguna de las dos (RF-183).

    Lo que ya esta en el entorno manda; el `.env` solo completa lo que falta.
    """
    entorno = os.environ if entorno is None else entorno
    del_fichero = leer_dotenv(FICHERO_DE_CLAVES if fichero is None else fichero)

    def valor(nombre: str) -> str:
        return (entorno.get(nombre) or del_fichero.get(nombre) or "").strip()

    publica = valor(VARIABLE_DE_LA_CLAVE_PUBLICA)
    secreta = valor(VARIABLE_DE_LA_CLAVE_SECRETA)
    if not publica or not secreta:
        return None
    return {
        "public_key": publica,
        "secret_key": secreta,
        "base_url": valor(VARIABLE_DEL_HOST) or HOST_POR_DEFECTO,
    }


def entorno_sin_langfuse(entorno: Mapping[str, str]) -> dict[str, str]:
    """El entorno sin ninguna variable `LANGFUSE_` (RF-191)."""
    return {
        clave: valor
        for clave, valor in entorno.items()
        if not clave.upper().startswith(PREFIJO_DE_LAS_VARIABLES)
    }


# --- Los identificadores, derivados y no guardados (D-78) --------------------


def sesion_de(id_obra: str | None, id_entrevista: str | None) -> str:
    """La sesion nace con la entrevista y la obra la hereda; sin entrevista, la
    obra es su propia sesion (RF-184)."""
    return str(id_entrevista or id_obra or "")


def _semilla(*partes: object) -> str:
    return ":".join(str(parte) for parte in partes)


def _id_de_traza(semilla: str) -> str:
    """El mismo que da `Langfuse.create_trace_id(seed=...)`: los 16 primeros
    bytes del sha256 de la semilla. Se calcula aqui para no cargar el SDK sin
    claves."""
    return hashlib.sha256(semilla.encode("utf-8")).digest()[:16].hex()


def id_de_traza(id_obra: str, version: int) -> str:
    """La traza de una version de la obra: la misma tras una caida (RF-184)."""
    return _id_de_traza(_semilla("obra", id_obra, "version", version))


def id_de_traza_de_entrevista(id_entrevista: str) -> str:
    return _id_de_traza(_semilla("entrevista", id_entrevista))


def id_de_score_de_la_puerta(id_obra: str, version: int, validador: str) -> str:
    """Volver a pasar la puerta sustituye el score, no lo repite (RF-187)."""
    return _id_de_traza(_semilla("puerta", id_obra, version, validador))


# --- Lo que se usa del SDK ---------------------------------------------------


@dataclass
class PromptVersionado:
    """Un prompt tal como esta en Langfuse (RF-189)."""

    texto: str
    version: int
    # El objeto del SDK, para enlazar la generacion con su version.
    del_sdk: Any = None


class Observacion(Protocol):
    id: str

    def update(self, **campos: Any) -> Any: ...

    def end(self) -> Any: ...


class Cliente(Protocol):
    """La cara estrecha del SDK que usa este modulo. En las pruebas, un fingido."""

    def abrir(
        self,
        *,
        traza: str,
        padre: str | None,
        nombre: str,
        tipo: str,
        sesion: str,
        nombre_de_traza: str,
        campos: dict[str, Any],
    ) -> Observacion: ...

    def score(self, **campos: Any) -> None: ...

    def prompt(self, nombre: str) -> PromptVersionado | None: ...

    def crear_prompt(self, nombre: str, texto: str) -> PromptVersionado: ...

    def vaciar(self) -> None: ...


class ClienteLangfuse:
    """El SDK de Python v4 de verdad. Manda por OpenTelemetry en segundo plano."""

    def __init__(self, **configuracion: Any) -> None:
        from langfuse import Langfuse, propagate_attributes

        self._sdk = Langfuse(**configuracion)
        self._propagar = propagate_attributes

    def abrir(
        self,
        *,
        traza: str,
        padre: str | None,
        nombre: str,
        tipo: str,
        sesion: str,
        nombre_de_traza: str,
        campos: dict[str, Any],
    ) -> Observacion:
        contexto: dict[str, str] = {"trace_id": traza}
        if padre:
            contexto["parent_span_id"] = padre
        # La sesion y el nombre de la traza viajan en cada observacion: en v4
        # son atributos que se propagan a lo que se abre dentro.
        with self._propagar(session_id=sesion, trace_name=nombre_de_traza):
            observacion: Observacion = self._sdk.start_observation(
                trace_context=contexto,  # type: ignore[arg-type]
                name=nombre,
                as_type=tipo,  # type: ignore[arg-type]
                **campos,
            )
        return observacion

    def score(self, **campos: Any) -> None:
        self._sdk.create_score(**campos)

    def prompt(self, nombre: str) -> PromptVersionado | None:
        try:
            leido = self._sdk.get_prompt(
                nombre,
                label=ETIQUETA_DE_LOS_PROMPTS,
                type="text",
                max_retries=0,
                fetch_timeout_seconds=ESPERA_DE_LOS_PROMPTS_EN_SEGUNDOS,
            )
        except Exception as error:  # noqa: BLE001
            if type(error).__name__ == "NotFoundError":
                return None
            raise
        return PromptVersionado(
            texto=str(leido.prompt), version=int(leido.version), del_sdk=leido
        )

    def crear_prompt(self, nombre: str, texto: str) -> PromptVersionado:
        creado = self._sdk.create_prompt(
            name=nombre,
            prompt=texto,
            labels=[ETIQUETA_DE_LOS_PROMPTS],
            type="text",
            commit_message="prompt.md del repositorio",
        )
        return PromptVersionado(texto=texto, version=int(creado.version), del_sdk=creado)

    def vaciar(self) -> None:
        self._sdk.flush()


# --- La observacion ----------------------------------------------------------


def _sin_romper[**P, R](metodo: Callable[P, R]) -> Callable[P, R | None]:
    """Un fallo de Langfuse se anota y se traga: la novela sigue (RF-190).

    Apagada, no hace nada. El aviso sale una vez por metodo y proceso, para no
    llenar el registro si Langfuse se cae a mitad de una obra.
    """

    @functools.wraps(metodo)
    def envuelto(*args: P.args, **kwargs: P.kwargs) -> R | None:
        propia = args[0]
        if not isinstance(propia, Observabilidad) or propia.cliente is None:
            return None
        try:
            return metodo(*args, **kwargs)
        except Exception as error:  # noqa: BLE001
            if metodo.__name__ not in propia._avisados:
                propia._avisados.add(metodo.__name__)
                registro.warning("Langfuse fallo en %s: %s", metodo.__name__, error)
            return None

    return envuelto


def _recortar(valor: Any, tope: int = TOPE_DE_LO_QUE_SE_MANDA_EN_CARACTERES) -> Any:
    if valor is None:
        return None
    texto = valor if isinstance(valor, str) else repr(valor)
    return texto if len(texto) <= tope else texto[:tope] + "…"


def _nombre_de_traza(titulo: str | None, version: int) -> str:
    return f"{titulo or 'obra'} · v{version}"


class Observabilidad:
    """Lo que se manda a Langfuse. Sin cliente, cada metodo vuelve sin hacer nada."""

    def __init__(
        self, cliente: Cliente | None = None, *, leer_prompt: Callable[[str], str] | None = None
    ) -> None:
        self.cliente = cliente
        self.leer_prompt = leer_prompt
        self._abiertas: dict[str, tuple[Observacion, dict[str, Any]]] = {}
        self._capitulos: dict[tuple[str, int, int], Observacion] = {}
        # Tarea -> la version del prompt que su texto tiene en Langfuse, o nada si
        # no se pudo: tambien el fallo se recuerda, para no esperar otra vez.
        self._prompts: dict[str, PromptVersionado | None] = {}
        self._cerrojo = threading.Lock()
        self._cerrojo_de_prompts = threading.Lock()
        self._avisados: set[str] = set()

    @property
    def activa(self) -> bool:
        return self.cliente is not None

    def _abrir(
        self,
        *,
        traza: str,
        padre: str | None,
        nombre: str,
        tipo: str,
        sesion: str,
        nombre_de_traza: str,
        **campos: Any,
    ) -> Observacion:
        assert self.cliente is not None
        return self.cliente.abrir(
            traza=traza,
            padre=padre,
            nombre=nombre,
            tipo=tipo,
            sesion=sesion,
            nombre_de_traza=nombre_de_traza,
            campos={clave: valor for clave, valor in campos.items() if valor is not None},
        )

    # --- Los prompts (RF-188) -------------------------------------------------

    def _prompt_de(self, tarea: str) -> PromptVersionado | None:
        """La version en Langfuse del `prompt.md` de la tarea, subida si cambio.

        El repositorio es la fuente del texto (D-03): se compara por texto y,
        si no es el de la ultima version, se sube uno nuevo. Una vez por tarea
        y proceso, tambien si falla.
        """
        if self.cliente is None or self.leer_prompt is None:
            return None
        with self._cerrojo_de_prompts:
            if tarea in self._prompts:
                return self._prompts[tarea]
            self._prompts[tarea] = None
            texto = self.leer_prompt(tarea)
            actual = self.cliente.prompt(tarea)
            if actual is None or actual.texto != texto:
                actual = self.cliente.crear_prompt(tarea, texto)
            self._prompts[tarea] = actual
            return actual

    @_sin_romper
    def registrar_prompt(self, tarea: str) -> int | None:
        versionado = self._prompt_de(tarea)
        return versionado.version if versionado else None

    def registrar_prompts(self, tareas: Iterable[str]) -> dict[str, int | None]:
        """Cada tarea con la version que su prompt tiene ahora en Langfuse."""
        return {tarea: self.registrar_prompt(tarea) for tarea in tareas}

    def registrar_prompts_en_segundo_plano(
        self, tareas: Iterable[str]
    ) -> threading.Thread | None:
        """Al arrancar, sin que el arranque espere a la red (RF-188, RF-190)."""
        if not self.activa or self.leer_prompt is None:
            return None
        lista = list(tareas)
        hilo = threading.Thread(
            target=self.registrar_prompts, args=(lista,), name="prompts-a-langfuse", daemon=True
        )
        hilo.start()
        return hilo

    @_sin_romper
    def obtener_prompt(self, nombre: str) -> PromptVersionado | None:
        assert self.cliente is not None
        return self.cliente.prompt(nombre)

    # --- La produccion (RF-185, RF-186) --------------------------------------

    @_sin_romper
    def abrir_capitulo(
        self,
        id_obra: str,
        version: int,
        capitulo: int,
        *,
        id_entrevista: str | None = None,
        titulo: str | None = None,
    ) -> None:
        span = self._abrir(
            traza=id_de_traza(id_obra, version),
            padre=None,
            nombre=f"capitulo {capitulo}",
            tipo="span",
            sesion=sesion_de(id_obra, id_entrevista),
            nombre_de_traza=_nombre_de_traza(titulo, version),
            metadata={"id_obra": id_obra, "version": version, "capitulo": capitulo},
        )
        with self._cerrojo:
            anterior = self._capitulos.pop((id_obra, version, capitulo), None)
            self._capitulos[(id_obra, version, capitulo)] = span
        if anterior is not None:
            anterior.update(level="WARNING", status_message="se rehizo desde el paso 1")
            anterior.end()

    @_sin_romper
    def cerrar_capitulo(
        self, id_obra: str, version: int, capitulo: int, totales: dict[str, Any]
    ) -> None:
        with self._cerrojo:
            span = self._capitulos.pop((id_obra, version, capitulo), None)
        if span is None:
            return
        span.update(
            output=totales,
            metadata={"id_obra": id_obra, "version": version, "capitulo": capitulo,
                      "totales": totales},
        )
        span.end()

    @_sin_romper
    def abrir_tarea(
        self,
        id_traza: str,
        *,
        id_obra: str,
        version: int,
        rol: str,
        tarea: str,
        intento: int,
        capitulo: int | None = None,
        escena: str | None = None,
        dimension: str | None = None,
        tokens_estimados: int | None = None,
        id_entrevista: str | None = None,
        titulo: str | None = None,
    ) -> None:
        with self._cerrojo:
            capitulo_abierto = (
                self._capitulos.get((id_obra, version, capitulo)) if capitulo else None
            )
        contexto = {
            "traza": id_de_traza(id_obra, version),
            "sesion": sesion_de(id_obra, id_entrevista),
            "nombre_de_traza": _nombre_de_traza(titulo, version),
        }
        generacion = self._abrir(
            **contexto,
            padre=capitulo_abierto.id if capitulo_abierto is not None else None,
            nombre=f"{rol} · {tarea}",
            tipo="generation",
            metadata={
                "id_obra": id_obra,
                "version": version,
                "id_traza": id_traza,
                "rol": rol,
                "tarea": tarea,
                "intento": intento,
                "capitulo": capitulo,
                "escena": escena,
                "dimension": dimension,
                "tokens_de_entrada_estimados": tokens_estimados,
            },
        )
        with self._cerrojo:
            self._abiertas[id_traza] = (generacion, contexto | {"id_obra": id_obra,
                                                                "tarea": tarea})

    @_sin_romper
    def cerrar_tarea(
        self,
        id_traza: str,
        *,
        salida: str | None = None,
        tokens_de_entrada: int | None = None,
        tokens_de_salida: int | None = None,
        coste: float | None = None,
        latencia_ms: int | None = None,
        modelo: str | None = None,
        herramientas: list[dict[str, Any]] | None = None,
        ganchos: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._cerrojo:
            abierta = self._abiertas.pop(id_traza, None)
        if abierta is None:
            return
        generacion, contexto = abierta
        uso = {
            clave: int(valor)
            for clave, valor in (("input", tokens_de_entrada), ("output", tokens_de_salida))
            if valor is not None
        }
        campos: dict[str, Any] = {
            "output": _recortar(salida),
            "model": modelo,
            "usage_details": uso or None,
            "cost_details": {"total": float(coste)} if coste is not None else None,
            "metadata": {"latencia_ms": latencia_ms},
        }
        versionado = self._prompts_sin_romper(contexto["tarea"])
        if versionado is not None and versionado.del_sdk is not None:
            campos["prompt"] = versionado.del_sdk
        if error:
            campos["level"] = "ERROR"
            campos["status_message"] = _recortar(error, TOPE_DEL_COMENTARIO_EN_CARACTERES)
        generacion.update(**{clave: v for clave, v in campos.items() if v is not None})
        for llamada in herramientas or []:
            hija = self._abrir(
                traza=contexto["traza"],
                padre=generacion.id,
                nombre=f"herramienta · {llamada.get('nombre') or '?'}",
                tipo="tool",
                sesion=contexto["sesion"],
                nombre_de_traza=contexto["nombre_de_traza"],
                input=_recortar(llamada.get("entrada")),
                output=_recortar(llamada.get("salida")),
                level="ERROR" if llamada.get("error") else None,
            )
            hija.end()
        for final in (ganchos or {}).get("final") or []:
            self._score(
                traza=contexto["traza"],
                observacion=generacion.id,
                nombre=f"gancho.{final.get('gancho')}",
                valor=1.0 if final.get("pasa") else 0.0,
                comentario="; ".join(str(m) for m in final.get("motivos") or []) or None,
            )
        generacion.end()

    def _prompts_sin_romper(self, tarea: str) -> PromptVersionado | None:
        try:
            return self._prompt_de(tarea)
        except Exception as error:  # noqa: BLE001
            registro.warning("Langfuse no dio la version del prompt %s: %s", tarea, error)
            return None

    @_sin_romper
    def version_terminada(
        self,
        id_obra: str,
        version: int,
        *,
        totales_de_la_version: dict[str, Any],
        totales_de_la_novela: dict[str, Any],
        id_entrevista: str | None = None,
        titulo: str | None = None,
    ) -> None:
        """Los totales de la version y los de la novela entera (RF-186)."""
        evento = self._abrir(
            traza=id_de_traza(id_obra, version),
            padre=None,
            nombre="version terminada",
            tipo="event",
            sesion=sesion_de(id_obra, id_entrevista),
            nombre_de_traza=_nombre_de_traza(titulo, version),
            output={"version": totales_de_la_version, "novela": totales_de_la_novela},
            metadata={
                "id_obra": id_obra,
                "version": version,
                "totales_de_la_version": totales_de_la_version,
                "totales_de_la_novela": totales_de_la_novela,
            },
        )
        evento.end()

    @_sin_romper
    def soltar(self, id_obra: str) -> None:
        """Lo que la obra deja abierto al parar el caminante se cierra como
        interrumpido: si no se cierra, no se manda."""
        with self._cerrojo:
            tareas = [c for c, (_, ctx) in self._abiertas.items() if ctx["id_obra"] == id_obra]
            observaciones = [self._abiertas.pop(c)[0] for c in tareas]
            capitulos = [c for c in self._capitulos if c[0] == id_obra]
            observaciones += [self._capitulos.pop(c) for c in capitulos]
        for observacion in observaciones:
            observacion.update(level="WARNING", status_message="interrumpida")
            observacion.end()

    # --- La entrevista (RF-185) ----------------------------------------------

    @_sin_romper
    def abrir_pasada(self, clave: str, id_entrevista: str) -> None:
        contexto = {
            "traza": id_de_traza_de_entrevista(id_entrevista),
            "sesion": sesion_de(None, id_entrevista),
            "nombre_de_traza": f"entrevista {id_entrevista}",
        }
        generacion = self._abrir(
            **contexto,
            padre=None,
            nombre="entrevistador · entrevistar",
            tipo="generation",
            metadata={"id_entrevista": id_entrevista},
        )
        with self._cerrojo:
            self._abiertas[clave] = (
                generacion,
                contexto | {"id_obra": id_entrevista, "tarea": "entrevistar"},
            )

    # --- Los validadores como scores (RF-187) --------------------------------

    def _score(
        self,
        *,
        traza: str,
        nombre: str,
        valor: float,
        comentario: str | None,
        observacion: str | None = None,
        id_score: str | None = None,
    ) -> None:
        assert self.cliente is not None
        campos: dict[str, Any] = {
            "name": nombre,
            "value": float(valor),
            "trace_id": traza,
            "data_type": "NUMERIC",
        }
        if comentario:
            campos["comment"] = _recortar(comentario, TOPE_DEL_COMENTARIO_EN_CARACTERES)
        if observacion:
            campos["observation_id"] = observacion
        if id_score:
            campos["score_id"] = id_score
        self.cliente.score(**campos)

    @_sin_romper
    def enviar_score(
        self, id_obra: str, version: int, nombre: str, valor: float, comentario: str
    ) -> None:
        """Un score en la traza de esa version de esa obra (RF-189)."""
        self._score(
            traza=id_de_traza(id_obra, version),
            nombre=nombre,
            valor=valor,
            comentario=comentario,
        )

    @_sin_romper
    def resultado_de_la_puerta(
        self,
        id_obra: str,
        version: int,
        fallos: list[dict[str, Any]],
        comprobacion_formal: str,
        validadores: Iterable[str] = VALIDADOR_DE_LA_PUERTA,
    ) -> None:
        """Un score por validador: 1 sin fallos, 0 con ellos. La cronologia, solo
        si hubo comprobacion formal."""
        for validador in validadores:
            if validador == "cronologia" and comprobacion_formal == "sin_comprobacion":
                continue
            suyos = [f for f in fallos if f.get("validador") == validador]
            detalle = "; ".join(
                f"capitulo {f.get('capitulo')}: {f.get('detalle')}"
                if f.get("capitulo") is not None
                else str(f.get("detalle"))
                for f in suyos
            )
            self._score(
                traza=id_de_traza(id_obra, version),
                nombre=f"puerta.{validador}",
                valor=0.0 if suyos else 1.0,
                comentario=detalle or None,
                id_score=id_de_score_de_la_puerta(id_obra, version, validador),
            )

    @_sin_romper
    def vaciar(self) -> None:
        assert self.cliente is not None
        self.cliente.vaciar()


# --- La instalacion ----------------------------------------------------------

_actual: Observabilidad | None = None
_cerrojo_de_la_instalacion = threading.Lock()


def desde_el_entorno() -> Observabilidad:
    """Encendida si hay claves; apagada si no, o si el SDK no arranca."""
    encontradas = claves()
    if encontradas is None:
        return Observabilidad()
    try:
        return Observabilidad(ClienteLangfuse(**encontradas))
    except Exception as error:  # noqa: BLE001
        registro.warning("Langfuse no arranco; se sigue sin observacion: %s", error)
        return Observabilidad()


def actual() -> Observabilidad:
    """La de este proceso, creada la primera vez que se pide."""
    global _actual
    with _cerrojo_de_la_instalacion:
        if _actual is None:
            _actual = desde_el_entorno()
        return _actual


def instalar(observabilidad: Observabilidad | None) -> Observabilidad | None:
    """Cambia la del proceso y devuelve la anterior. `None` vuelve a leer el
    entorno la proxima vez. Es lo que usan las pruebas (RF-192)."""
    global _actual
    with _cerrojo_de_la_instalacion:
        anterior, _actual = _actual, observabilidad
        return anterior


def obtener_prompt(nombre: str) -> PromptVersionado | None:
    """El prompt `nombre` de Langfuse, o nada si esta apagado o no existe."""
    return actual().obtener_prompt(nombre)


def enviar_score(
    id_obra: str, version: int, nombre: str, valor: float, comentario: str
) -> None:
    """Cuelga un score de la traza de esa version de esa obra; apagado, nada."""
    actual().enviar_score(id_obra, version, nombre, valor, comentario)
