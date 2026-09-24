"""Los dos hooks de los subagentes de prosa (SPEC1 4.13).

Son hooks `Stop` de Claude Code de verdad: el ejecutor los pone en la orden de
cada subagente que escribe prosa, y el CLI los lanza cuando el agente va a
terminar. Cada uno es este mismo modulo:

    python -m novela.ganchos <gancho> <tarea>

Lee de la entrada que le da Claude Code el ultimo mensaje del agente y si ya ha
bloqueado en ese turno. Si lo entregado no pasa, sale con codigo 2 y el motivo
por la salida de error: el CLI se lo devuelve al agente, que tiene que corregir
y volver a entregar. Si pasa, sale con 0.

**No abre la base de datos, no escribe nada en disco y no llama a ningun
modelo.** El esquema y el contrato los lee de `tareas/`, que es entrada
versionada; la lista de vetos y la reserva de la vuelta le llegan en variables
de entorno. Quien registra el veredicto es el ejecutor: el almacen sigue con un
solo escritor.

Las comprobaciones son funciones puras y el ejecutor las vuelve a aplicar, con
estas mismas funciones, a lo que el agente entrego al final: ese es el
veredicto que cuenta (RF-126). Anadir una comprobacion es anadir una funcion a
su lista, sin tocar el enganche.
"""

import json
import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

from novela.ajustes import CARACTERES_POR_TOKEN_ESTIMADOS
from novela.tareas import contrato_de_tarea, esquema_de_tarea
from novela.vocabularios import GANCHOS

# Lo que el ejecutor le pasa al hook por el entorno del subagente (D-46).
VARIABLE_DE_VETOS = "NOVELA_GANCHO_VETOS"
VARIABLE_DE_RESERVA = "NOVELA_GANCHO_RESERVA"

# Con esto empieza todo lo que dice un hook: es lo que permite al agente saber
# que el mensaje es del sistema y al ejecutor saber de que hook es cada evento.
PREFIJO = "[novela:"

# El motivo que se reinyecta al agente no pasa de aqui (RF-125).
TOPE_DEL_MOTIVO_EN_CARACTERES = 1_000
# El CLI encabeza el motivo con la linea de orden del hook: se cuenta aparte.
TOPE_DE_LA_CABECERA_EN_CARACTERES = 300

SALIDA_PASA = 0
SALIDA_BLOQUEA = 2

Entrega = dict[str, Any]
Comprobacion = Callable[[Entrega, str], list[str]]


class EntregaIlegible(ValueError):
    """Lo que el agente entrego no es un objeto JSON."""


def leer_entrega(texto: str) -> Entrega:
    """El agente devuelve JSON; a veces lo envuelve en vallas de codigo."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[-1]
        if limpio.rstrip().endswith("```"):
            limpio = limpio.rstrip()[: -len("```")]
    try:
        devuelto = json.loads(limpio)
    except json.JSONDecodeError as error:
        raise EntregaIlegible(f"el agente no devolvio JSON: {texto[:200]!r}") from error
    if not isinstance(devuelto, dict):
        raise EntregaIlegible("el agente devolvio JSON que no es un objeto")
    return devuelto


def _artefactos(entrega: Entrega) -> list[Any]:
    artefactos = entrega.get("artefactos")
    return artefactos if isinstance(artefactos, list) else []


def _textos_de_prosa(entrega: Entrega) -> list[str]:
    """El `texto` de cada `Borrador` y cada `Parrafo`: la prosa entregada."""
    textos: list[str] = []
    for artefacto in _artefactos(entrega):
        if not isinstance(artefacto, dict):
            continue
        cuerpo = artefacto.get("cuerpo")
        if artefacto.get("tipo") in ("Borrador", "Parrafo") and isinstance(cuerpo, dict):
            texto = cuerpo.get("texto")
            if isinstance(texto, str):
                textos.append(texto)
    return textos


# --- validar_capitulo: la forma, nada del contenido (RF-123) -----------------


def _trae_la_lista_de_artefactos(entrega: Entrega, tarea: str) -> list[str]:
    if not isinstance(entrega.get("artefactos"), list):
        return ["falta la lista `artefactos`"]
    return []


def _cada_artefacto_con_tipo_y_cuerpo(entrega: Entrega, tarea: str) -> list[str]:
    fallos: list[str] = []
    for posicion, artefacto in enumerate(_artefactos(entrega), start=1):
        if not isinstance(artefacto, dict):
            fallos.append(f"el artefacto {posicion} no es un objeto")
            continue
        if not isinstance(artefacto.get("tipo"), str):
            fallos.append(f"el artefacto {posicion} no declara su `tipo`")
        if not isinstance(artefacto.get("cuerpo"), dict):
            fallos.append(f"el artefacto {posicion} no trae `cuerpo`")
    return fallos


def _solo_tipos_que_el_rol_escribe(entrega: Entrega, tarea: str) -> list[str]:
    permitidos = set(contrato_de_tarea(tarea)["escribe"])
    ajenos = sorted(
        {
            artefacto["tipo"]
            for artefacto in _artefactos(entrega)
            if isinstance(artefacto, dict)
            and isinstance(artefacto.get("tipo"), str)
            and artefacto["tipo"] not in permitidos
        }
    )
    return [f"`{tipo}` no es un tipo que esta tarea escriba" for tipo in ajenos]


def _entrega_el_tipo_de_su_esquema(entrega: Entrega, tarea: str) -> list[str]:
    esquema = json.loads(esquema_de_tarea(tarea))
    tipo = esquema["tipo"]
    campos = list(esquema.get("cuerpo", {}))
    candidatos = [
        artefacto["cuerpo"]
        for artefacto in _artefactos(entrega)
        if isinstance(artefacto, dict)
        and artefacto.get("tipo") == tipo
        and isinstance(artefacto.get("cuerpo"), dict)
    ]
    if not candidatos:
        return [f"falta el `{tipo}` que esta tarea entrega"]
    fallos: list[str] = []
    for cuerpo in candidatos:
        faltan = [campo for campo in campos if campo not in cuerpo]
        if faltan:
            fallos.append(f"al `{tipo}` le faltan {', '.join(f'`{c}`' for c in faltan)}")
    return fallos


def _borradores_con_texto(entrega: Entrega, tarea: str) -> list[str]:
    vacios = sum(
        1
        for artefacto in _artefactos(entrega)
        if isinstance(artefacto, dict)
        and artefacto.get("tipo") == "Borrador"
        and isinstance(artefacto.get("cuerpo"), dict)
        and not (
            isinstance(artefacto["cuerpo"].get("texto"), str)
            and artefacto["cuerpo"]["texto"].strip()
        )
    )
    return [f"{vacios} `Borrador` sin `texto`"] if vacios else []


# La lista a la que se suman comprobaciones sin tocar el enganche (D-48).
COMPROBACIONES_DE_CAPITULO: list[Comprobacion] = [
    _trae_la_lista_de_artefactos,
    _cada_artefacto_con_tipo_y_cuerpo,
    _solo_tipos_que_el_rol_escribe,
    _entrega_el_tipo_de_su_esquema,
    _borradores_con_texto,
]


# --- policy: lo vetado, tal cual (RF-124) ------------------------------------


def coincidencias(texto: str, vetos: Sequence[str]) -> list[str]:
    """Lo vetado que aparece en el texto, como subcadena exacta.

    Sin normalizar: ni mayusculas, ni acentos, ni plurales (D-49).
    """
    return [veto for veto in vetos if veto and veto in texto]


def _sin_nada_vetado(entrega: Entrega, vetos: Sequence[str]) -> list[str]:
    encontrados: list[str] = []
    for texto in _textos_de_prosa(entrega):
        for veto in coincidencias(texto, vetos):
            if veto not in encontrados:
                encontrados.append(veto)
    return [f"aparece lo vetado: «{veto}»" for veto in encontrados]


# --- El veredicto -----------------------------------------------------------


def revisar(gancho: str, tarea: str, texto: str, vetos: Sequence[str] = ()) -> list[str]:
    """Lo que no pasa de lo entregado, segun ese hook. Vacio si pasa.

    Es la funcion que usan a la vez el hook, dentro de la sesion, y el ejecutor,
    al terminar: el mismo veredicto no puede salir de dos sitios distintos.
    """
    if gancho not in GANCHOS:
        raise ValueError(f"{gancho!r} no es un gancho declarado")
    try:
        entrega = leer_entrega(texto)
    except EntregaIlegible as error:
        # Si no se puede leer, no hay prosa en la que buscar nada vetado: eso
        # lo dice el hook de la forma.
        return [str(error)] if gancho == "validar_capitulo" else []
    if gancho == "policy":
        return _sin_nada_vetado(entrega, vetos)
    fallos: list[str] = []
    for comprobacion in COMPROBACIONES_DE_CAPITULO:
        fallos.extend(comprobacion(entrega, tarea))
    return fallos


def motivo(gancho: str, fallos: Sequence[str]) -> str:
    """Lo que se le devuelve al agente, acotado (RF-125)."""
    que_hacer = (
        "Reescribe esos pasajes sin ello"
        if gancho == "policy"
        else "Corrige la forma de lo que entregas"
    )
    texto = (
        f"{PREFIJO}{gancho}] Lo que has entregado no pasa: {'; '.join(fallos)}. "
        f"{que_hacer} y vuelve a entregar el objeto JSON entero, sin texto alrededor."
    )
    if len(texto) <= TOPE_DEL_MOTIVO_EN_CARACTERES:
        return texto
    return texto[: TOPE_DEL_MOTIVO_EN_CARACTERES - 1] + "…"


def _tokens(caracteres: int) -> int:
    return int(caracteres / CARACTERES_POR_TOKEN_ESTIMADOS) + 1


def cabe_la_vuelta(texto_entregado: str, reserva: int) -> bool:
    """Si la vuelta de correccion cabe en la reserva del paso (RF-128).

    La vuelta vuelve a leer la respuesta anterior y el motivo de cada hook que
    bloquee, con su cabecera. Se cuenta el peor caso: que bloqueen todos.
    """
    por_motivo = _tokens(TOPE_DEL_MOTIVO_EN_CARACTERES + TOPE_DE_LA_CABECERA_EN_CARACTERES)
    return _tokens(len(texto_entregado)) + len(GANCHOS) * por_motivo <= reserva


def _vetos_del_entorno() -> list[str]:
    bruto = os.environ.get(VARIABLE_DE_VETOS, "")
    if not bruto:
        return []
    try:
        vetos = json.loads(bruto)
    except json.JSONDecodeError:
        return []
    return [veto for veto in vetos if isinstance(veto, str)] if isinstance(vetos, list) else []


def _reserva_del_entorno() -> int:
    try:
        return int(os.environ.get(VARIABLE_DE_RESERVA, "0"))
    except ValueError:
        return 0


def principal(argumentos: Sequence[str], entrada: str) -> tuple[int, str, str]:
    """El hook entero: devuelve el codigo de salida, la salida y la de error.

    Separado de la entrada y la salida del proceso para poder probarlo dandole
    lo mismo que le daria Claude Code.
    """
    if len(argumentos) != 2:
        return SALIDA_PASA, "", "uso: python -m novela.ganchos <gancho> <tarea>"
    gancho, tarea = argumentos
    try:
        datos = json.loads(entrada) if entrada.strip() else {}
    except json.JSONDecodeError:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    if datos.get("stop_hook_active"):
        # Ya hubo una vuelta en este turno: una por intento (RF-125). Lo que
        # quede lo juzga el ejecutor.
        return SALIDA_PASA, f"{PREFIJO}{gancho}] ya hubo vuelta: decide el ejecutor", ""
    texto = datos.get("last_assistant_message") or ""
    if not isinstance(texto, str):
        texto = ""
    fallos = revisar(gancho, tarea, texto, _vetos_del_entorno())
    if not fallos:
        return SALIDA_PASA, f"{PREFIJO}{gancho}] pasa", ""
    if not cabe_la_vuelta(texto, _reserva_del_entorno()):
        return (
            SALIDA_PASA,
            f"{PREFIJO}{gancho}] no pasa y la vuelta no cabe en la reserva: decide el ejecutor",
            "",
        )
    return SALIDA_BLOQUEA, "", motivo(gancho, fallos)


def main() -> None:  # pragma: no cover - es la envoltura del proceso
    # Claude Code habla en UTF-8 aunque la consola de Windows no lo haga: un veto
    # con acento tiene que casar igual.
    entrada = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    codigo, salida, error = principal(sys.argv[1:], entrada)
    if salida:
        sys.stdout.buffer.write(salida.encode("utf-8"))
    if error:
        sys.stderr.buffer.write(error.encode("utf-8"))
    sys.exit(codigo)


if __name__ == "__main__":  # pragma: no cover
    main()
