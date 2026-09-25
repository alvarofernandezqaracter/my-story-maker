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
versionada; la lista de vetos —la global y la del comprador, cada veto con su
nivel—, los nombres de la biblia y la reserva de la vuelta le llegan en
variables de entorno. Quien registra el veredicto es el ejecutor y quien lo
escribe, el almacen, que sigue con un solo escritor.

Las comprobaciones son funciones puras y el ejecutor las vuelve a aplicar, con
estas mismas funciones, a lo que el agente entrego al final: ese es el
veredicto que cuenta (RF-126). Anadir una comprobacion es anadir una funcion a
su lista, sin tocar el enganche.
"""

import json
import os
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from novela import validadores
from novela.ajustes import CARACTERES_POR_TOKEN_ESTIMADOS
from novela.tareas import contrato_de_tarea, esquema_de_tarea
from novela.vocabularios import GANCHOS, NIVEL_DE_VETO

# Lo que el ejecutor le pasa al hook por el entorno del subagente (D-46).
VARIABLE_DE_VETOS = "NOVELA_GANCHO_VETOS"
VARIABLE_DE_RESERVA = "NOVELA_GANCHO_RESERVA"
# Los nombres de la biblia, para escribirlos tal cual (SPEC1 RF-145).
VARIABLE_DE_NOMBRES = "NOVELA_GANCHO_NOMBRES"

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


@dataclass(frozen=True)
class DatosDeLaObra:
    """Lo que una comprobacion necesita saber de la obra, llegado por el entorno.

    No es la ventana: al agente no le llega nada de esto salvo lo que una
    comprobacion le diga de su propio texto.
    """

    nombres: tuple[str, ...] = ()


Comprobacion = Callable[[Entrega, str, DatosDeLaObra], list[str]]


class EntregaIlegible(ValueError):
    """Lo que el agente entrego no es un objeto JSON."""


VALLA = "```"


def _candidatos(texto: str) -> list[str]:
    """Donde puede estar el objeto, por orden (SPEC1 RF-211): la respuesta
    entera, el primer bloque entre vallas y de la primera llave a la ultima."""
    limpio = texto.strip()
    candidatos = [limpio]
    apertura = limpio.find(VALLA)
    if apertura != -1:
        dentro = limpio[apertura + len(VALLA) :].split("\n", 1)[-1]
        cierre = dentro.find(VALLA)
        candidatos.append(dentro if cierre == -1 else dentro[:cierre])
    primera, ultima = limpio.find("{"), limpio.rfind("}")
    if primera != -1 and ultima > primera:
        candidatos.append(limpio[primera : ultima + 1])
    return candidatos


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in descompuesto if not unicodedata.combining(letra))


def _tipos_sin_tildes(entrega: Entrega) -> Entrega:
    """`Crítica` se lee `Critica`: ningun tipo del almacen lleva tilde (SPEC1
    RF-212). Solo el envoltorio; el cuerpo queda como vino."""
    artefactos = entrega.get("artefactos")
    if not isinstance(artefactos, list):
        return entrega
    leidos = [
        artefacto | {"tipo": _sin_tildes(artefacto["tipo"])}
        if isinstance(artefacto, dict) and isinstance(artefacto.get("tipo"), str)
        else artefacto
        for artefacto in artefactos
    ]
    return entrega | {"artefactos": leidos}


def leer_entrega(texto: str) -> Entrega:
    """El agente devuelve JSON; a veces lo envuelve en vallas de codigo o le
    pone texto alrededor. Vale el primer candidato que sea un objeto."""
    error: json.JSONDecodeError | None = None
    for candidato in _candidatos(texto):
        try:
            devuelto = json.loads(candidato)
        except json.JSONDecodeError as fallo:
            error = error or fallo
            continue
        if isinstance(devuelto, dict):
            return _tipos_sin_tildes(devuelto)
    if error is None:
        raise EntregaIlegible("el agente devolvio JSON que no es un objeto")
    raise EntregaIlegible(
        f"el agente no devolvio JSON ({error.msg}, caracter {error.pos} de "
        f"{len(texto.strip())}): empieza {texto.strip()[:160]!r} y acaba "
        f"{texto.strip()[-160:]!r}"
    )


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


def _trae_la_lista_de_artefactos(
    entrega: Entrega, tarea: str, datos: DatosDeLaObra
) -> list[str]:
    if not isinstance(entrega.get("artefactos"), list):
        return ["falta la lista `artefactos`"]
    return []


def _cada_artefacto_con_tipo_y_cuerpo(
    entrega: Entrega, tarea: str, datos: DatosDeLaObra
) -> list[str]:
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


def _solo_tipos_que_el_rol_escribe(
    entrega: Entrega, tarea: str, datos: DatosDeLaObra
) -> list[str]:
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


def _entrega_el_tipo_de_su_esquema(
    entrega: Entrega, tarea: str, datos: DatosDeLaObra
) -> list[str]:
    esquema = json.loads(esquema_de_tarea(tarea))
    # Un ejemplo, o una lista: el tipo que se entrega es el del primero, y sus
    # campos obligatorios son los que traen todos sus ejemplos (SPEC1 RF-208).
    ejemplos = esquema if isinstance(esquema, list) else [esquema]
    tipo = ejemplos[0]["tipo"]
    obligatorios = validadores.campos_por_tipo(esquema).get(tipo, set())
    campos = [campo for campo in ejemplos[0].get("cuerpo", {}) if campo in obligatorios]
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


def _borradores_con_texto(entrega: Entrega, tarea: str, datos: DatosDeLaObra) -> list[str]:
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


def _nombres_como_en_la_biblia(entrega: Entrega, tarea: str, datos: DatosDeLaObra) -> list[str]:
    """Los nombres de la biblia se escriben tal cual (RF-142, RF-145)."""
    encontrados: list[tuple[str, str]] = []
    for texto in _textos_de_prosa(entrega):
        for par in validadores.nombres_mal_escritos(texto, datos.nombres):
            if par not in encontrados:
                encontrados.append(par)
    return [
        f"«{escrito}» no es como lo escribe la biblia: es «{nombre}»"
        for escrito, nombre in encontrados
    ]


# La lista a la que se suman comprobaciones sin tocar el enganche (D-48).
COMPROBACIONES_DE_CAPITULO: list[Comprobacion] = [
    _trae_la_lista_de_artefactos,
    _cada_artefacto_con_tipo_y_cuerpo,
    _solo_tipos_que_el_rol_escribe,
    _entrega_el_tipo_de_su_esquema,
    _borradores_con_texto,
    _nombres_como_en_la_biblia,
]


# --- policy: lo vetado, normalizado (RF-124, SPEC1 4.14) -------------------


@dataclass(frozen=True)
class Veto:
    """Un termino vetado y la lista de la que sale (RF-130)."""

    termino: str
    nivel: str


@dataclass(frozen=True)
class Coincidencia:
    """Un veto que aparece en la prosa, y como aparece escrito alli."""

    veto: Veto
    encontrado: str


# Una palabra: letras o cifras seguidas. Lo demas separa.
_PALABRA = re.compile(r"[^\W_]+")
# Tres o mas veces la misma letra seguida no existe en espanol: es enfasis.
_LETRA_ALARGADA = re.compile(r"(.)\1{2,}")
# Consonantes tras las que el plural es `-es`: «animal» → «animales».
_PLURAL_EN_ES = "lnrdjyz"


def _sin_acentos(palabra: str) -> str:
    """Minusculas y sin tildes ni dieresis. La `ñ` es otra letra y se queda."""
    letras: list[str] = []
    for letra in unicodedata.normalize("NFC", palabra).casefold():
        if letra == "ñ":
            letras.append(letra)
            continue
        descompuesta = unicodedata.normalize("NFD", letra)
        letras.append("".join(c for c in descompuesta if not unicodedata.combining(c)))
    return "".join(letras)


def reducir(palabra: str) -> str:
    """La forma con la que se compara una palabra, igual en los dos lados (RF-132).

    Reglas fijas y nada mas (D-52): minusculas y sin acentos, la letra alargada
    como una, sin plural y sin la vocal de genero. Dos palabras que solo
    difieren en eso casan; es lo que se busca y es tambien su precio.
    """
    forma = _LETRA_ALARGADA.sub(r"\1", _sin_acentos(palabra))
    if len(forma) > 3 and forma.endswith("s"):
        forma = forma[:-1]
    if len(forma) > 3 and forma.endswith("ce"):
        forma = forma[:-2] + "z"  # «lapices» → «lapiz»
    elif len(forma) > 3 and forma.endswith("e") and forma[-2] in _PLURAL_EN_ES:
        forma = forma[:-1]  # «animales» → «animal»
    if len(forma) > 3 and forma[-1] in "ao":
        forma = forma[:-1]  # «tonta», «tonto» → «tont»
    return forma


def palabras(texto: str) -> list[str]:
    return _PALABRA.findall(unicodedata.normalize("NFC", texto))


def veto_del_comprador(termino: str) -> Veto:
    """Un veto del brief es palabra o tema segun cuantas palabras tiene (D-50)."""
    nivel = "palabra_del_comprador" if len(palabras(termino)) <= 1 else "tema_del_comprador"
    return Veto(termino=termino, nivel=nivel)


def _como_veto(veto: Veto | str) -> Veto:
    return veto if isinstance(veto, Veto) else veto_del_comprador(veto)


def coincidencias(texto: str, vetos: Sequence[Veto | str]) -> list[Coincidencia]:
    """Lo vetado que aparece en el texto, por palabras enteras y normalizado.

    Un veto casa cuando sus palabras reducidas aparecen seguidas en el texto,
    y un tema es eso mismo con mas de una palabra (RF-133). Una sola vez cada
    veto con cada forma escrita distinta.
    """
    texto = unicodedata.normalize("NFC", texto)
    tramos = [(m.start(), m.end(), reducir(m.group())) for m in _PALABRA.finditer(texto)]
    formas = [forma for _, _, forma in tramos]
    halladas: list[Coincidencia] = []
    for bruto in vetos:
        veto = _como_veto(bruto)
        buscadas = [reducir(palabra) for palabra in palabras(veto.termino)]
        if not buscadas:
            continue
        largo = len(buscadas)
        for inicio in range(len(formas) - largo + 1):
            if formas[inicio : inicio + largo] == buscadas:
                escrito = texto[tramos[inicio][0] : tramos[inicio + largo - 1][1]]
                coincidencia = Coincidencia(veto=veto, encontrado=escrito)
                if coincidencia not in halladas:
                    halladas.append(coincidencia)
    return halladas


def coincidencias_en_la_entrega(
    texto_entregado: str, vetos: Sequence[Veto | str]
) -> list[Coincidencia]:
    """Lo vetado en la prosa de lo que entrego el agente. Vacio si no se lee."""
    try:
        entrega = leer_entrega(texto_entregado)
    except EntregaIlegible:
        return []
    halladas: list[Coincidencia] = []
    for texto in _textos_de_prosa(entrega):
        for coincidencia in coincidencias(texto, vetos):
            if coincidencia not in halladas:
                halladas.append(coincidencia)
    return halladas


def _sin_nada_vetado(entrega: Entrega, vetos: Sequence[Veto | str]) -> list[str]:
    """El motivo nombra lo que el agente escribio, no la lista (RF-134)."""
    encontrados: list[str] = []
    for texto in _textos_de_prosa(entrega):
        for coincidencia in coincidencias(texto, vetos):
            if coincidencia.encontrado not in encontrados:
                encontrados.append(coincidencia.encontrado)
    return [f"aparece lo vetado: «{escrito}»" for escrito in encontrados]


# --- El veredicto -----------------------------------------------------------


def revisar(
    gancho: str,
    tarea: str,
    texto: str,
    vetos: Sequence[Veto | str] = (),
    *,
    nombres: Sequence[str] = (),
) -> list[str]:
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
    datos = DatosDeLaObra(nombres=tuple(nombres))
    for comprobacion in COMPROBACIONES_DE_CAPITULO:
        fallos.extend(comprobacion(entrega, tarea, datos))
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


def vetos_para_el_entorno(vetos: Sequence[Veto | str]) -> str:
    """La lista tal como viaja al hook: cada veto con su nivel (RF-134).

    En ASCII escapado: el entorno de un proceso en Windows no garantiza UTF-8.
    """
    return json.dumps(
        [{"termino": v.termino, "nivel": v.nivel} for v in map(_como_veto, vetos)]
    )


def _vetos_del_entorno() -> list[Veto]:
    """Lo contrario de `vetos_para_el_entorno`. Una cadena suelta es del comprador."""
    bruto = os.environ.get(VARIABLE_DE_VETOS, "")
    if not bruto:
        return []
    try:
        vetos = json.loads(bruto)
    except json.JSONDecodeError:
        return []
    if not isinstance(vetos, list):
        return []
    leidos: list[Veto] = []
    for veto in vetos:
        if isinstance(veto, str):
            leidos.append(veto_del_comprador(veto))
        elif (
            isinstance(veto, dict)
            and isinstance(veto.get("termino"), str)
            and veto.get("nivel") in NIVEL_DE_VETO
        ):
            leidos.append(Veto(termino=veto["termino"], nivel=veto["nivel"]))
    return leidos


def _nombres_del_entorno() -> list[str]:
    try:
        nombres = json.loads(os.environ.get(VARIABLE_DE_NOMBRES, "") or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(nombres, list):
        return []
    return [nombre for nombre in nombres if isinstance(nombre, str)]


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
    fallos = revisar(gancho, tarea, texto, _vetos_del_entorno(), nombres=_nombres_del_entorno())
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
