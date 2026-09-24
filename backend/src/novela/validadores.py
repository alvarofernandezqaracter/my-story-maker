"""Los validadores programaticos (SPEC1 4.15).

Funciones puras: reciben lo que ya se ha leido y devuelven lo que falla. No
abren la base de datos, no escriben en disco y no llaman a ningun modelo, asi
que las pueden usar a la vez el hook `validar_capitulo`, dentro de la sesion del
subagente, y la puerta de publicacion, en `nucleo.versiones` (RF-140).

No juzgan el texto: cuentan palabras y comparan cadenas contra lo escrito en la
biblia y en el esquema de cada tarea (D-56).
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

# Una palabra es una racha de letras o digitos; lo demas la separa.
_PALABRA = re.compile(r"[^\W_]+", re.UNICODE)

# Por debajo de estas longitudes, una letra de diferencia es demasiado a menudo
# otra palabra corriente: «Pero» frente a «Pedro» (D-56).
LETRAS_PARA_UNA_SUSTITUCION = 5
LETRAS_PARA_UNA_DE_MAS_O_DE_MENOS = 7
LETRAS_PARA_SOLO_ACENTOS = 3


def palabras(texto: str) -> int:
    """Cuantas palabras tiene un texto (RF-143)."""
    return len(_PALABRA.findall(texto))


def longitud_fuera_de_rango(total: int, minimo: int, maximo: int) -> str | None:
    """El motivo si `total` no cae entre `minimo` y `maximo`, o nada si cae."""
    if total < minimo:
        return f"tiene {total} palabras y el minimo es {minimo}"
    if total > maximo:
        return f"tiene {total} palabras y el maximo es {maximo}"
    return None


# --- Esquema (RF-141) --------------------------------------------------------


def campos_por_tipo(esquema: Any) -> dict[str, set[str]]:
    """Que campos declara el esquema de una tarea para cada tipo que escribe.

    El `esquema.json` es un ejemplo del artefacto, o una lista de ejemplos
    cuando la tarea escribe mas de un tipo.
    """
    ejemplos = esquema if isinstance(esquema, list) else [esquema]
    campos: dict[str, set[str]] = {}
    for ejemplo in ejemplos:
        if not isinstance(ejemplo, dict) or not isinstance(ejemplo.get("tipo"), str):
            continue
        cuerpo = ejemplo.get("cuerpo")
        campos.setdefault(ejemplo["tipo"], set()).update(
            cuerpo if isinstance(cuerpo, dict) else ()
        )
    return campos


def campos_que_faltan(esquema: Any, tipo: str, cuerpo: dict[str, Any]) -> list[str] | None:
    """Los campos del esquema que le faltan a un cuerpo, en orden.

    `None` si el esquema no declara ese tipo: entonces no hay nada que mirar.
    """
    declarados = campos_por_tipo(esquema).get(tipo)
    if declarados is None:
        return None
    return sorted(campo for campo in declarados if campo not in cuerpo)


# --- Nombres (RF-142) --------------------------------------------------------


def _sin_acentos(palabra: str) -> str:
    descompuesta = unicodedata.normalize("NFD", palabra)
    return "".join(letra for letra in descompuesta if not unicodedata.combining(letra))


def _pliegue(palabra: str) -> str:
    return _sin_acentos(palabra).casefold()


def _distancia(a: str, b: str) -> int:
    """Distancia de edicion: letras cambiadas, de mas o de menos."""
    anterior = list(range(len(b) + 1))
    for i, letra_a in enumerate(a, start=1):
        actual = [i]
        for j, letra_b in enumerate(b, start=1):
            actual.append(
                min(
                    anterior[j] + 1,
                    actual[j - 1] + 1,
                    anterior[j - 1] + (letra_a != letra_b),
                )
            )
        anterior = actual
    return anterior[-1]


def _se_parece(escrita: str, nombre: str) -> bool:
    """Si `escrita` es `nombre` mal escrito, con las reglas de D-56."""
    a, b = _pliegue(escrita), _pliegue(nombre)
    if a == b:
        return len(b) >= LETRAS_PARA_SOLO_ACENTOS
    if len(a) == len(b):
        return len(b) >= LETRAS_PARA_UNA_SUSTITUCION and _distancia(a, b) == 1
    return (
        abs(len(a) - len(b)) == 1
        and len(b) >= LETRAS_PARA_UNA_DE_MAS_O_DE_MENOS
        and _distancia(a, b) == 1
    )


def palabras_de_los_nombres(nombres: Iterable[str]) -> list[str]:
    """Las palabras con mayuscula de cada nombre: «Ines de Salcedo» da dos."""
    vistas: list[str] = []
    for nombre in nombres:
        for palabra in _PALABRA.findall(nombre):
            if palabra[0].isupper() and palabra not in vistas:
                vistas.append(palabra)
    return vistas


def nombres_mal_escritos(texto: str, nombres: Sequence[str]) -> list[tuple[str, str]]:
    """Cada palabra del texto que parece un nombre de la biblia mal escrito.

    Devuelve pares (lo escrito, el nombre de la biblia), sin repetir. Una
    palabra que tambien sale en minuscula en el mismo texto es una palabra
    corriente y no se toma por nombre.
    """
    conocidas = palabras_de_los_nombres(nombres)
    if not conocidas:
        return []
    exactas = set(conocidas)
    escritas = _PALABRA.findall(texto)
    en_minuscula = {palabra for palabra in escritas if palabra[0].islower()}
    encontrados: list[tuple[str, str]] = []
    for palabra in escritas:
        if not palabra[0].isupper() or palabra in exactas:
            continue
        if palabra.lower() in en_minuscula:
            continue
        for nombre in conocidas:
            if _se_parece(palabra, nombre):
                par = (palabra, nombre)
                if par not in encontrados:
                    encontrados.append(par)
                break
    return encontrados


def aparece_tal_cual(nombre: str, textos: Iterable[str]) -> bool:
    """Si el nombre sale escrito exactamente asi, como palabras enteras."""
    patron = re.compile(r"(?<![^\W_])" + re.escape(nombre) + r"(?![^\W_])", re.UNICODE)
    return any(patron.search(texto) for texto in textos)
