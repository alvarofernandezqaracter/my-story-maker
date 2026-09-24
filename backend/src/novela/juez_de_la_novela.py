"""El juez de la novela: un evaluador externo que puntua una version terminada.

Puntua tres cosas de la novela entera (SPEC1 4.21): que lo que viene del
destinatario este metido con naturalidad, que funcione como novela y que siga
siendo de su epoca. Nota y justificacion por criterio, y cada nota va como
score a la traza de esa version en Langfuse.

**No es un rol del censo** (D-83). No tiene carpeta en `tareas/`, no escribe
nada en el almacen, no esta en el guion ni en la API y su nota no dispara nada:
si la produccion pudiera reaccionar a ella, aprenderia a complacerle.

**Su rubrica no esta en el repositorio.** Llega de Langfuse, por la
observabilidad que recibe como parametro, y sin ella no se juzga: aqui no hay
rubrica por defecto ni se lee de ningun fichero (RF-194, RF-202). Lo que este
modulo sabe del juez es lo que dice la spec: los tres criterios, lo que recibe,
la forma de lo que devuelve y donde cuelga sus notas.
"""

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from novela.ajustes import (
    INTENTOS_DEL_JUEZ_DE_LA_NOVELA,
    MODELO_DEL_JUEZ_DE_LA_NOVELA,
    TOPE_DE_VENTANA_DEL_JUEZ_DE_LA_NOVELA,
)
from novela.almacen import Almacen
from novela.ejecutor import CatalogoDeTareas, EjecutorDeSubagentes, SubagenteFallo
from novela.nucleo.caminante import Ejecutor, Resultado
from novela.nucleo.guion import Encargo
from novela.nucleo.presupuesto import estimar_tokens
from novela.nucleo.proyecciones import Ventana
from novela.vocabularios import CRITERIO_DEL_JUEZ_DE_LA_NOVELA, EVALUADORES_EXTERNOS

NOMBRE_DEL_PROMPT = "juez-de-la-novela"
ROL = "juez_de_la_novela"
TAREA = "juzgar_la_novela"
PREFIJO_DEL_SCORE = "juez_de_la_novela."
NOTA_MINIMA = 1
NOTA_MAXIMA = 5
PROYECCION: tuple[str, ...] = (
    "encargo",
    "criterios_que_se_puntuan",
    "hechos_personales",
    "resumenes_de_capitulo",
    "capitulos_leidos",
    "capitulos_no_leidos",
)

assert ROL in EVALUADORES_EXTERNOS

# La forma de lo que devuelve, no la vara con que juzga: saberla no ensena a
# complacer a nadie. Va en la instruccion de sistema, detras de la rubrica.
FORMA_DEL_VEREDICTO = json.dumps(
    {
        "artefactos": [],
        "constancia": {
            "criterios": [
                {
                    "criterio": "uno de criterios_que_se_puntuan",
                    "nota": f"entero de {NOTA_MINIMA} a {NOTA_MAXIMA}",
                    "justificacion": "por que esa nota",
                    "citas": ["fragmento literal de los datos del encargo"],
                }
            ]
        },
    },
    ensure_ascii=False,
    indent=1,
)

# Lo que no puede cerrar la marca que lo encierra: si pudiera, lo que viniera
# detras dejaria de ser dato.
_MARCAS_QUE_NO_SE_CIERRAN = ("</capitulo", "</datos_del_encargo")


class PromptVersionado(Protocol):
    """Un prompt de Langfuse: su texto y la version que se sirvio."""

    @property
    def texto(self) -> str: ...

    @property
    def version(self) -> int: ...


class Observabilidad(Protocol):
    """Lo unico que el juez necesita de Langfuse (RF-200).

    `obtener_prompt` devuelve `None` si Langfuse esta apagado o el prompt no
    existe; `enviar_score` cuelga el score de la traza de esa version y no hace
    nada si Langfuse esta apagado.
    """

    def obtener_prompt(self, nombre: str) -> PromptVersionado | None: ...

    def enviar_score(
        self, id_obra: str, version: int, nombre: str, valor: float, comentario: str
    ) -> None: ...


CrearEjecutor = Callable[[CatalogoDeTareas, str], Ejecutor]


class JuicioNoLanzado(Exception):
    """El juicio no se lanza, y el motivo dice por que. No se ha gastado nada."""


class RubricaNoDisponible(JuicioNoLanzado):
    """Sin rubrica de Langfuse no se juzga (RF-194)."""


class JuicioInvalido(Exception):
    """El juez contesto, pero ningun intento dio un veredicto que valga (RF-198)."""

    def __init__(self, motivos: list[str]) -> None:
        super().__init__(
            "el juez de la novela no dio un veredicto valido: " + "; ".join(motivos)
        )
        self.motivos = motivos


@dataclass(frozen=True)
class _CatalogoDelJuez:
    """La instruccion de sistema del juez: la rubrica de Langfuse y la forma."""

    rubrica: str

    def prompt(self, tarea: str, dimension: str | None) -> str:
        return self.rubrica

    def esquema(self, tarea: str) -> str:
        return FORMA_DEL_VEREDICTO


def _ejecutor_de_verdad(catalogo: CatalogoDeTareas, modelo: str) -> Ejecutor:
    return EjecutorDeSubagentes(catalogo=catalogo, modelo=modelo)


@dataclass
class Juicio:
    """Lo que devuelve un juicio valido, ademas de lo que fue a Langfuse."""

    id_obra: str
    version: int
    version_de_la_rubrica: int
    notas: list[dict[str, Any]]
    capitulos_leidos: list[int]
    capitulos_no_leidos: list[int]
    intentos: int
    tokens_de_entrada_estimados: int
    tokens_de_entrada_medidos: int | None
    tokens_de_salida: int | None
    coste: float | None
    latencia_ms: int
    artefactos_ignorados: int = 0
    scores: list[str] = field(default_factory=list)


# --- Que criterios se puntuan y que recibe --------------------------------


def criterios_que_se_puntuan(obra: dict[str, Any]) -> tuple[str, ...]:
    """Sin destinatario no hay personalizacion que juzgar (RF-195)."""
    if obra.get("destinatario"):
        return CRITERIO_DEL_JUEZ_DE_LA_NOVELA
    return tuple(c for c in CRITERIO_DEL_JUEZ_DE_LA_NOVELA if c != "personalizacion_integrada")


def _encargo_de_la_obra(obra: dict[str, Any]) -> dict[str, Any]:
    """El brief que juzga: sin los vetos del destinatario, que no le tocan."""
    encargo = {
        clave: obra[clave]
        for clave in ("titulo", "epoca", "premisa", "tesis_tematica")
        if obra.get(clave)
    }
    destinatario = obra.get("destinatario")
    if isinstance(destinatario, dict):
        encargo["destinatario"] = {
            clave: valor for clave, valor in destinatario.items() if clave != "vetos"
        }
    return encargo


def _neutralizar(texto: str) -> str:
    for marca in _MARCAS_QUE_NO_SE_CIERRAN:
        texto = texto.replace(marca, marca.replace("<", "&lt;"))
    return texto


def prioridad_de_los_capitulos(
    capitulos: Iterable[int], con_lo_personal: Iterable[int]
) -> list[int]:
    """El primero, el ultimo, los que usan lo personal y el resto en orden (D-85)."""
    todos = sorted(set(capitulos))
    if not todos:
        return []
    orden = [todos[0], todos[-1], *sorted(set(con_lo_personal)), *todos]
    vistos: list[int] = []
    for capitulo in orden:
        if capitulo in todos and capitulo not in vistos:
            vistos.append(capitulo)
    return vistos


def _texto_de_la_ventana(
    fijo: list[str], textos: dict[int, str], leidos: Sequence[int]
) -> str:
    no_leidos = [c for c in sorted(textos) if c not in leidos]
    partes = [
        *fijo,
        "capitulos_no_leidos: " + json.dumps(no_leidos),
        "capitulos_leidos:",
        *(
            f'<capitulo numero="{capitulo}">\n{textos[capitulo]}\n</capitulo>'
            for capitulo in sorted(leidos)
        ),
    ]
    return "\n\n".join(partes)


def ventana_del_juicio(
    obra: dict[str, Any],
    resumenes: Sequence[dict[str, Any]],
    textos_por_capitulo: dict[int, str],
    hechos_personales: Sequence[dict[str, Any]],
    *,
    tope: int = TOPE_DE_VENTANA_DEL_JUEZ_DE_LA_NOVELA,
) -> Ventana:
    """Arma y mide la ventana del juez (RF-196).

    Los capitulos entran enteros, por prioridad, mientras quepan en el tope; los
    que no caben se saltan y la ventana los nombra. Si ni sin capitulos cabe, no
    se lanza: no se recorta ningun resumen.
    """
    criterios = criterios_que_se_puntuan(obra)
    textos = {c: _neutralizar(t) for c, t in textos_por_capitulo.items() if t}
    personales = [
        {"nombre": h.get("nombre"), "tipo": h.get("tipo"), "capitulos": h.get("capitulos", [])}
        for h in hechos_personales
    ]
    fijo = [
        "encargo:\n" + json.dumps(_encargo_de_la_obra(obra), ensure_ascii=False, indent=1),
        "criterios_que_se_puntuan: " + json.dumps(list(criterios)),
        "hechos_personales:\n" + json.dumps(personales, ensure_ascii=False, indent=1),
        "resumenes_de_capitulo:\n"
        + _neutralizar(json.dumps(list(resumenes), ensure_ascii=False, indent=1)),
    ]
    base = estimar_tokens(_texto_de_la_ventana(fijo, textos, []))
    if base > tope:
        raise JuicioNoLanzado(
            f"la ventana del juez no cabe ni sin capitulos: sobran {base - tope} tokens "
            f"de {tope}"
        )
    con_lo_personal = [c for h in personales for c in h["capitulos"]]
    leidos: list[int] = []
    for capitulo in prioridad_de_los_capitulos(textos, con_lo_personal):
        if estimar_tokens(_texto_de_la_ventana(fijo, textos, [*leidos, capitulo])) <= tope:
            leidos.append(capitulo)
    texto = _texto_de_la_ventana(fijo, textos, leidos)
    return Ventana(
        materiales={
            "encargo": _encargo_de_la_obra(obra),
            "criterios_que_se_puntuan": list(criterios),
            "hechos_personales": personales,
            "resumenes_de_capitulo": list(resumenes),
            "capitulos_leidos": sorted(leidos),
            "capitulos_no_leidos": [c for c in sorted(textos) if c not in leidos],
        },
        texto=texto,
        tokens=estimar_tokens(texto),
    )


# --- Lo que devuelve -------------------------------------------------------


def leer_veredicto(
    constancia: dict[str, Any] | None, criterios: Sequence[str], ventana: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Las notas, si el veredicto vale entero, y los motivos si no (RF-198).

    Vale entero o no vale: tres notas de una version van juntas, y una sola
    rota deja fuera las otras.
    """
    bruto = (constancia or {}).get("criterios")
    if not isinstance(bruto, list):
        return [], ["no trae `constancia.criterios`"]
    motivos: list[str] = []
    notas: list[dict[str, Any]] = []
    vistos: list[str] = []
    for elemento in bruto:
        if not isinstance(elemento, dict):
            motivos.append("un criterio no es un objeto")
            continue
        criterio = elemento.get("criterio")
        if criterio not in criterios:
            motivos.append(f"{criterio!r} no es un criterio que se puntue aqui")
            continue
        if criterio in vistos:
            motivos.append(f"{criterio} viene mas de una vez")
            continue
        vistos.append(criterio)
        nota = elemento.get("nota")
        if isinstance(nota, bool) or not isinstance(nota, int):
            motivos.append(f"{criterio}: la nota no es un entero")
        elif not NOTA_MINIMA <= nota <= NOTA_MAXIMA:
            motivos.append(
                f"{criterio}: la nota {nota} no esta entre {NOTA_MINIMA} y {NOTA_MAXIMA}"
            )
        justificacion = elemento.get("justificacion")
        if not isinstance(justificacion, str) or not justificacion.strip():
            motivos.append(f"{criterio}: sin justificacion")
        citas = elemento.get("citas")
        if not isinstance(citas, list) or not citas:
            motivos.append(f"{criterio}: sin citas")
            citas = []
        for cita in citas:
            if not isinstance(cita, str) or not cita.strip() or cita not in ventana:
                motivos.append(
                    f"{criterio}: la cita {cita!r} no aparece literal en lo que leyo"
                )
        notas.append(
            {"criterio": criterio, "nota": nota, "justificacion": justificacion, "citas": citas}
        )
    for criterio in criterios:
        if criterio not in vistos:
            motivos.append(f"falta el criterio {criterio}")
    return (notas if not motivos else []), motivos


def comentario_del_score(
    nota: dict[str, Any], rubrica: PromptVersionado, leidos: list[int], no_leidos: list[int]
) -> str:
    """Lo que acompana a la nota en Langfuse: el porque y con que rubrica (RF-199)."""
    citas = " · ".join(f"«{cita}»" for cita in nota["citas"])
    return (
        f"{nota['justificacion']}\n\nCitas: {citas}\n"
        f"Rubrica: {NOMBRE_DEL_PROMPT} v{rubrica.version}\n"
        f"Capitulos leidos: {', '.join(map(str, leidos)) or 'ninguno'}; "
        f"no leidos: {', '.join(map(str, no_leidos)) or 'ninguno'}"
    )


# --- El juicio --------------------------------------------------------------


def _hay_produccion_en_marcha(almacen: Almacen) -> bool:
    return any(almacen.trazas_abiertas(obra.id) for obra in almacen.listar_obras() if obra.id)


def _leer_la_version(
    almacen: Almacen, id_obra: str, version: int
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[int, str], list[dict[str, Any]]]:
    obra = almacen.leer_obra(id_obra)
    fila = almacen.leer_version(id_obra, version)
    if obra is None or fila is None:
        raise JuicioNoLanzado(f"la obra {id_obra} no tiene version {version}")
    if fila["terminada_en"] is None:
        raise JuicioNoLanzado(
            f"la version {version} de {id_obra} no ha terminado: solo se juzga lo terminado"
        )
    resumenes = [
        {"capitulo": r.capitulo, **r.cuerpo}
        for r in sorted(
            almacen.listar("ResumenCapitulo", id_obra, version=version),
            key=lambda r: r.capitulo or 0,
        )
    ]
    textos: dict[int, list[str]] = {}
    for borrador in almacen.manuscrito_aceptado(id_obra, version=version):
        texto = borrador.cuerpo.get("texto")
        if isinstance(texto, str) and borrador.capitulo is not None:
            textos.setdefault(borrador.capitulo, []).append(texto)
    personales = almacen.hechos_de_la_biblia(id_obra, licencia="personal", version=version)
    return (
        obra.cuerpo,
        resumenes,
        {capitulo: "\n\n".join(partes) for capitulo, partes in textos.items()},
        personales,
    )


def encargo_del_juicio(id_obra: str, intentos: int = INTENTOS_DEL_JUEZ_DE_LA_NOVELA) -> Encargo:
    """El juicio no es un paso del guion: va solo, sin hooks y sobre la obra."""
    return Encargo(
        paso=0,
        tarea=TAREA,
        rol=ROL,
        unidad="obra",
        proyeccion=PROYECCION,
        id_obra=id_obra,
        reintentos=intentos,
    )


def juzgar_version(
    almacen: Almacen,
    id_obra: str,
    version: int,
    *,
    observabilidad: Observabilidad,
    crear_ejecutor: CrearEjecutor = _ejecutor_de_verdad,
    intentos: int = INTENTOS_DEL_JUEZ_DE_LA_NOVELA,
) -> Juicio:
    """Juzga una version terminada y cuelga sus notas en Langfuse (RF-193 a RF-199).

    Sin rubrica, sin version terminada o con produccion en marcha no se lanza
    nada. Solo un veredicto valido entero manda scores; si ningun intento lo da,
    no se manda ninguno y se dice por que.
    """
    rubrica = observabilidad.obtener_prompt(NOMBRE_DEL_PROMPT)
    if rubrica is None or not rubrica.texto.strip():
        raise RubricaNoDisponible(
            f"falta la rubrica del juez de la novela: el prompt `{NOMBRE_DEL_PROMPT}` no "
            "llega de Langfuse (apagado, sin claves o sin ese prompt). No se juzga con "
            "una rubrica inventada ni sacada del repositorio"
        )
    obra, resumenes, textos, personales = _leer_la_version(almacen, id_obra, version)
    if _hay_produccion_en_marcha(almacen):
        raise JuicioNoLanzado(
            "hay produccion en marcha en la instalacion: el juez de la novela solo se "
            "lanza cuando no hay ninguna traza abierta, para caber en el techo (RF-197)"
        )
    ventana = ventana_del_juicio(obra, resumenes, textos, personales)
    criterios = criterios_que_se_puntuan(obra)
    encargo = encargo_del_juicio(id_obra, intentos)
    ejecutor = crear_ejecutor(_CatalogoDelJuez(rubrica.texto), MODELO_DEL_JUEZ_DE_LA_NOVELA)

    motivos: list[str] = []
    for intento in range(1, intentos + 1):
        try:
            resultado: Resultado = ejecutor.ejecutar(encargo, ventana)
        except SubagenteFallo as error:
            motivos = [f"intento {intento}: {error}"]
            continue
        notas, rotos = leer_veredicto(resultado.constancia, criterios, ventana.texto)
        if rotos:
            motivos = [f"intento {intento}: {motivo}" for motivo in rotos]
            continue
        return _mandar(
            observabilidad, id_obra, version, rubrica, ventana, notas, resultado, intento
        )
    raise JuicioInvalido(motivos)


def _mandar(
    observabilidad: Observabilidad,
    id_obra: str,
    version: int,
    rubrica: PromptVersionado,
    ventana: Ventana,
    notas: list[dict[str, Any]],
    resultado: Resultado,
    intento: int,
) -> Juicio:
    leidos = list(ventana.materiales["capitulos_leidos"])
    no_leidos = list(ventana.materiales["capitulos_no_leidos"])
    juicio = Juicio(
        id_obra=id_obra,
        version=version,
        version_de_la_rubrica=rubrica.version,
        notas=notas,
        capitulos_leidos=leidos,
        capitulos_no_leidos=no_leidos,
        intentos=intento,
        tokens_de_entrada_estimados=ventana.tokens,
        tokens_de_entrada_medidos=resultado.tokens_de_entrada_medidos,
        tokens_de_salida=resultado.tokens_de_salida,
        coste=resultado.coste,
        latencia_ms=resultado.latencia_ms,
        # El juez no escribe nada: lo que devuelva como artefacto se cuenta y
        # no se guarda (RF-198, RD-34).
        artefactos_ignorados=len(resultado.artefactos),
    )
    for nota in notas:
        nombre = PREFIJO_DEL_SCORE + nota["criterio"]
        observabilidad.enviar_score(
            id_obra,
            version,
            nombre,
            float(nota["nota"]),
            comentario_del_score(nota, rubrica, leidos, no_leidos),
        )
        juicio.scores.append(nombre)
    return juicio
