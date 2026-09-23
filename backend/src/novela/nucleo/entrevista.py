"""La pasada de entrevista: su ventana, y quedarse con lo que vale de lo que vuelve.

El Entrevistador completa el brief antes de que la obra exista (SPEC1 4.8).
Cada pasada arranca en frio: la ventana la trae la persona en ese momento y de
las pasadas anteriores no llega nada (D-20).

Aqui no se juzga nada del dominio. Que un tono no case con una edad lo juzga el
Entrevistador; lo que se hace aqui es mecanico y se puede comprobar sin leer:

- **La cita es literal o no hay hecho.** Un hecho cuya cita no aparece tal cual
  en un texto pegado se descarta (RF-74), y un recuerdo se guarda con su cita,
  no con una parafrasis (RF-75).
- **Lo que la persona escribio manda.** Un escalar presente no se toca, y en las
  listas solo se anade detras (RF-73).
- **Una contradiccion sin evidencia no llega a nadie** (RF-76), igual que una
  `Critica` sin evidencia no llega al Revisor.

Que campos tiene el brief no se decide aqui: lo dice el modelo del borde HTTP,
que es el unico sitio con tipos, y quien llama pasa sus rutas.
"""

import copy
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from novela.nucleo.guion import Encargo
from novela.nucleo.presupuesto import estimar_tokens
from novela.nucleo.proyecciones import Ventana
from novela.vocabularios import TIPO_DE_CONTRADICCION

TAREA = "entrevistar"
ROL = "entrevistador"
PROYECCION: tuple[str, ...] = (
    "borrador_de_brief",
    "textos_pegados",
    "contradicciones_asumidas",
)

RUTA_DE_LOS_RECUERDOS = "destinatario.recuerdos"

# Cada texto pegado va dentro de su propia marca, dentro de los datos del
# encargo que ya delimita el ejecutor. Es dato, nunca instruccion (RF-74).
APERTURA_DE_TEXTO = '<texto_pegado numero="{numero}">'
CIERRE_DE_TEXTO = "</texto_pegado>"

# Un texto pegado no puede cerrar la marca que lo encierra ni la del encargo:
# si pudiera, lo que viniera detras dejaria de ser dato.
_MARCAS_QUE_NO_SE_CIERRAN = ("</texto_pegado", "</datos_del_encargo")


def encargo() -> Encargo:
    """La pasada no pertenece al guion de ninguna obra: va sola y antes."""
    return Encargo(paso=0, tarea=TAREA, rol=ROL, unidad="brief", proyeccion=PROYECCION)


def neutralizar(texto: str) -> str:
    """El texto tal como lo vera el agente, sin forma de cerrar su marca."""
    for marca in _MARCAS_QUE_NO_SE_CIERRAN:
        texto = texto.replace(marca, marca.replace("<", "&lt;"))
    return texto


def ventana(
    borrador: dict[str, Any], textos: Iterable[str], asumidas: Iterable[str]
) -> Ventana:
    """Arma la ventana de una pasada. Se mide aqui, antes de mandarla."""
    vistos = [neutralizar(texto) for texto in textos]
    asumidas = list(asumidas)
    partes = [
        "borrador_de_brief:\n" + json.dumps(borrador, ensure_ascii=False, indent=1),
        "contradicciones_asumidas: " + json.dumps(asumidas, ensure_ascii=False),
        "textos_pegados:",
        *(
            f"{APERTURA_DE_TEXTO.format(numero=numero)}\n{texto}\n{CIERRE_DE_TEXTO}"
            for numero, texto in enumerate(vistos, start=1)
        ),
    ]
    texto = "\n\n".join(partes)
    return Ventana(
        materiales={
            "borrador_de_brief": borrador,
            "textos_pegados": vistos,
            "contradicciones_asumidas": asumidas,
        },
        texto=texto,
        tokens=estimar_tokens(texto),
    )


@dataclass
class Propuesta:
    """Lo que queda de una pasada despues de filtrar lo que devolvio el agente.

    `aportados` son los escalares que puso el agente, con el hecho del que
    salen: si el modelo del brief no los admite, se quitan y el campo sigue
    faltando (RF-73).
    """

    brief: dict[str, Any]
    hechos: list[dict[str, Any]] = field(default_factory=list)
    hechos_descartados: list[dict[str, Any]] = field(default_factory=list)
    contradicciones: list[dict[str, Any]] = field(default_factory=list)
    contradicciones_descartadas: list[dict[str, Any]] = field(default_factory=list)
    aportados: dict[str, dict[str, Any]] = field(default_factory=dict)

    def retirar(self, ruta: str, motivo: str) -> None:
        """Quita un escalar que puso el agente y deja constancia del descarte."""
        hecho = self.aportados.pop(ruta)
        _quitar(self.brief, ruta)
        self.hechos.remove(hecho)
        self.hechos_descartados.append(_descarte(hecho, motivo))


def aplicar_pasada(
    borrador: dict[str, Any],
    textos: Iterable[str],
    constancia: dict[str, Any] | None,
    *,
    escalares: frozenset[str],
    listas: frozenset[str],
    asumidas: Iterable[str] = (),
) -> Propuesta:
    """Funde lo que la persona escribio con lo que el agente extrajo."""
    vistos = [neutralizar(texto) for texto in textos]
    asumidas = set(asumidas)
    devuelto = constancia or {}
    propuesta = Propuesta(brief=copy.deepcopy(borrador))

    for hecho in _lista(devuelto.get("hechos")):
        motivo = _aplicar_hecho(propuesta, hecho, vistos, escalares, listas)
        if motivo:
            propuesta.hechos_descartados.append(_descarte(hecho, motivo))

    for contradiccion in _lista(devuelto.get("contradicciones")):
        motivo = _motivo_para_descartar(
            contradiccion, propuesta.brief, borrador, vistos, escalares | listas
        )
        if motivo:
            propuesta.contradicciones_descartadas.append(
                {"contradiccion": contradiccion, "motivo": motivo}
            )
            continue
        propuesta.contradicciones.append(
            {
                "tipo": contradiccion["tipo"],
                "campos": list(contradiccion["campos"]),
                "evidencia": contradiccion["evidencia"],
                "asumida": contradiccion["tipo"] in asumidas,
            }
        )
    return propuesta


# --- Los hechos -------------------------------------------------------------


def _aplicar_hecho(
    propuesta: Propuesta,
    hecho: Any,
    textos: list[str],
    escalares: frozenset[str],
    listas: frozenset[str],
) -> str | None:
    """Aplica el hecho o devuelve por que se descarta."""
    if not isinstance(hecho, dict):
        return "no es un hecho"
    campo = hecho.get("campo")
    if not isinstance(campo, str) or campo not in escalares | listas:
        return "el campo no es uno de los del brief"
    cita = hecho.get("cita")
    if not isinstance(cita, str) or not cita.strip():
        return "no trae cita"
    if not any(cita in texto for texto in textos):
        return "la cita no aparece literal en ningun texto pegado"

    # Un recuerdo se guarda tal como la persona lo entrego (RF-75).
    valor = cita if campo == RUTA_DE_LOS_RECUERDOS else hecho.get("valor")
    if valor is None or valor == "":
        return "no trae valor"
    aceptado = {"campo": campo, "valor": valor, "cita": cita}

    if campo in escalares:
        if _presente(propuesta.brief, campo):
            return "la persona ya escribio ese campo"
        _poner(propuesta.brief, campo, valor)
        propuesta.aportados[campo] = aceptado
    else:
        if not isinstance(valor, str) or not valor.strip():
            return "no es un valor que admita la lista"
        actual = _leer(propuesta.brief, campo)
        if actual is None:
            actual = []
            _poner(propuesta.brief, campo, actual)
        if not isinstance(actual, list):
            return "el campo de la persona no es una lista"
        if valor in actual:
            return "ya esta en la lista"
        actual.append(valor)
    propuesta.hechos.append(aceptado)
    return None


def _descarte(hecho: Any, motivo: str) -> dict[str, Any]:
    if not isinstance(hecho, dict):
        return {"campo": None, "cita": None, "motivo": motivo}
    campo, cita = hecho.get("campo"), hecho.get("cita")
    return {
        "campo": campo if isinstance(campo, str) else None,
        "cita": cita if isinstance(cita, str) else None,
        "motivo": motivo,
    }


# --- Las contradicciones ------------------------------------------------------


def _motivo_para_descartar(
    contradiccion: Any,
    brief: dict[str, Any],
    borrador: dict[str, Any],
    textos: list[str],
    campos_del_brief: frozenset[str],
) -> str | None:
    if not isinstance(contradiccion, dict):
        return "no es una contradiccion"
    tipo = contradiccion.get("tipo")
    if tipo not in TIPO_DE_CONTRADICCION:
        return "tipo fuera de vocabulario"
    evidencia = contradiccion.get("evidencia")
    if not isinstance(evidencia, str) or not evidencia.strip():
        return "sin evidencia"
    campos = contradiccion.get("campos")
    if not isinstance(campos, list) or not campos:
        return "no nombra los campos en conflicto"
    if any(not isinstance(c, str) or c not in campos_del_brief for c in campos):
        return "nombra un campo que no es del brief"
    if tipo == "edad_contra_tono":
        necesarios = {"destinatario.edad", "destinatario.tono"}
        if not necesarios <= set(campos):
            return "no nombra la edad y el tono"
        if not all(_presente(brief, c) for c in necesarios):
            return "el brief no tiene edad y tono que contrastar"
    if tipo == "texto_contra_campo":
        if not any(evidencia in texto for texto in textos):
            return "la evidencia no aparece literal en ningun texto pegado"
        if not any(_presente(borrador, c) for c in campos):
            return "no nombra ningun campo que la persona escribiera"
    return None


# --- Rutas con punto sobre el brief -------------------------------------------


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _leer(brief: dict[str, Any], ruta: str) -> Any:
    actual: Any = brief
    for parte in ruta.split("."):
        if not isinstance(actual, dict):
            return None
        actual = actual.get(parte)
    return actual


def _presente(brief: dict[str, Any], ruta: str) -> bool:
    valor = _leer(brief, ruta)
    return valor is not None and valor != ""


def _poner(brief: dict[str, Any], ruta: str, valor: Any) -> None:
    *camino, ultimo = ruta.split(".")
    actual = brief
    for parte in camino:
        siguiente = actual.get(parte)
        if not isinstance(siguiente, dict):
            siguiente = {}
            actual[parte] = siguiente
        actual = siguiente
    actual[ultimo] = valor


def _quitar(brief: dict[str, Any], ruta: str) -> None:
    *camino, ultimo = ruta.split(".")
    actual: Any = brief
    for parte in camino:
        actual = actual.get(parte) if isinstance(actual, dict) else None
    if isinstance(actual, dict):
        actual.pop(ultimo, None)
