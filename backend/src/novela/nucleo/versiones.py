"""Las versiones de la obra: rehacer desde un capitulo y publicar (SPEC1 4.12).

Aqui no se decide nada del dominio: que capitulos cambian lo dice la orden del
editor, y lo que ve cada version lo deduce el almacen de dos numeros por fila.
Lo que se decide aqui es el orden de las cosas y que publicar pase por un solo
sitio, que es donde esta la puerta de publicacion (SPEC1 4.15).
"""

import json
from typing import Any, Protocol

from novela import validadores
from novela.almacen import Almacen
from novela.almacen.artefactos import VersionNoAdmitida
from novela.nucleo import guion
from novela.nucleo.caminante import IndiceDeLaObra
from novela.nucleo.proyecciones import nombres_de_la_biblia
from novela.vocabularios import TAREA_DE_ROL


class Esquemas(Protocol):
    """De donde sale el `esquema.json` de cada tarea: el catalogo de `tareas/`,
    que `nucleo` no importa."""

    def esquema(self, tarea: str) -> str: ...


class PuertaNoSuperada(Exception):
    """La version no pasa la puerta y no se publica (RF-146).

    Lleva el resultado entero: que fallo, de que validador y en que capitulo.
    """

    def __init__(self, resultado: dict[str, Any]) -> None:
        fallos = resultado["fallos"]
        super().__init__(
            f"la version {resultado['version']} de {resultado['id_obra']} no pasa la "
            f"puerta de publicacion: {len(fallos)} fallo(s)"
        )
        self.resultado = resultado


def rehacer_desde(
    almacen: Almacen,
    indice: IndiceDeLaObra | None,
    id_obra: str,
    desde: int,
    hasta: int,
) -> int:
    """Abre la version siguiente, que reescribe de `desde` a `hasta` (RF-111).

    La version anterior conserva su mundo; la nueva comparte los capitulos
    anteriores a `desde`. Lo relevado sale del indice, para que la produccion
    de la nueva no recupere como eco lo que ya no es suyo. Arrancar la
    produccion es cosa de quien llama, por el camino de siempre (RF-91).
    """
    if not 1 <= desde <= hasta:
        raise ValueError(f"el capitulo {desde} no esta entre 1 y {hasta}")
    nueva = almacen.abrir_version(id_obra, desde, hasta)
    if indice is not None:
        indice.retirar_desde(id_obra, desde)
    return nueva


def cambiar_hecho(
    almacen: Almacen,
    indice: IndiceDeLaObra | None,
    id_obra: str,
    hecho: str,
    valor: str,
) -> tuple[int, list[int]]:
    """El cambio del lector: abre la version que reescribe solo los capitulos
    que mencionan el hecho, con su nombre nuevo (SPEC1 RF-170 a RF-173).

    Que capitulos son lo dicen las menciones de la ultima version, no el texto.
    Lo relevado sale del indice, como al rehacer. Arrancar la produccion es cosa
    de quien llama, por el camino de siempre (RF-175).
    """
    nueva, capitulos = almacen.abrir_version_por_cambio(id_obra, hecho, valor)
    if indice is not None:
        indice.retirar_capitulos(id_obra, capitulos)
    return nueva, capitulos


# --- La puerta de publicacion (SPEC1 4.15) ---------------------------------


def _fallo(validador: str, capitulo: int | None, detalle: str) -> dict[str, Any]:
    return {"validador": validador, "capitulo": capitulo, "detalle": detalle}


def _esquema(
    almacen: Almacen, id_obra: str, numero: int, esquemas: Esquemas
) -> list[dict[str, Any]]:
    """RF-141: cada salida de rol que conserva la version trae su esquema."""
    leidos: dict[str, Any] = {}
    fallos = []
    for artefacto in almacen.salidas_de_rol_de_la_version(id_obra, numero):
        tarea = TAREA_DE_ROL.get(artefacto.procedencia_rol or "")
        if tarea is None:
            continue
        if tarea not in leidos:
            leidos[tarea] = json.loads(esquemas.esquema(tarea))
        faltan = validadores.campos_que_faltan(leidos[tarea], artefacto.tipo, artefacto.cuerpo)
        if faltan:
            fallos.append(
                _fallo(
                    "esquema",
                    artefacto.capitulo,
                    f"{artefacto.tipo} {artefacto.id}, de {tarea}, sin "
                    + ", ".join(f"`{campo}`" for campo in faltan),
                )
            )
    return fallos


def _textos_por_capitulo(
    almacen: Almacen, id_obra: str, numero: int, capitulos: int
) -> dict[int, list[str]]:
    textos: dict[int, list[str]] = {capitulo: [] for capitulo in range(1, capitulos + 1)}
    for borrador in almacen.manuscrito_aceptado(id_obra, version=numero):
        texto = borrador.cuerpo.get("texto")
        if isinstance(texto, str):
            textos.setdefault(borrador.capitulo or 0, []).append(texto)
    return textos


def _nombres(
    almacen: Almacen, id_obra: str, numero: int, textos: dict[int, list[str]]
) -> list[dict[str, Any]]:
    """RF-142: los nombres de la biblia, tal cual, y el del destinatario presente."""
    nombres = nombres_de_la_biblia(almacen, id_obra, version=numero)
    fallos = []
    for capitulo, del_capitulo in textos.items():
        vistos: list[tuple[str, str]] = []
        for texto in del_capitulo:
            for par in validadores.nombres_mal_escritos(texto, nombres):
                if par not in vistos:
                    vistos.append(par)
        fallos += [
            _fallo("nombres", capitulo, f"«{escrito}» donde la biblia escribe «{nombre}»")
            for escrito, nombre in vistos
        ]
    obra = almacen.leer_obra(id_obra)
    destinatario = obra.cuerpo.get("destinatario") if obra is not None else None
    if isinstance(destinatario, dict) and isinstance(destinatario.get("nombre"), str):
        nombre = destinatario["nombre"]
        todos = [texto for del_capitulo in textos.values() for texto in del_capitulo]
        if not validadores.aparece_tal_cual(nombre, todos):
            fallos.append(
                _fallo("nombres", None, f"el nombre del destinatario, «{nombre}», no aparece")
            )
    return fallos


def _longitud(textos: dict[int, list[str]]) -> list[dict[str, Any]]:
    """RF-143: cada capitulo cae dentro del rango del guion."""
    minimo, maximo = guion.PALABRAS_POR_CAPITULO
    fallos = []
    for capitulo, del_capitulo in sorted(textos.items()):
        total = sum(validadores.palabras(texto) for texto in del_capitulo)
        motivo = validadores.longitud_fuera_de_rango(total, minimo, maximo)
        if motivo is not None:
            fallos.append(_fallo("longitud", capitulo, f"el capitulo {motivo}"))
    return fallos


def _elementos_personalizados(
    almacen: Almacen, id_obra: str, numero: int
) -> list[dict[str, Any]]:
    """RF-144: todo hecho `personal` se usa en algun capitulo."""
    return [
        _fallo(
            "elementos_personalizados",
            None,
            f"{hecho['tipo']} {hecho['id']} «{hecho['nombre']}» no aparece en ningun capitulo",
        )
        for hecho in almacen.hechos_de_la_biblia(id_obra, licencia="personal", version=numero)
        if not hecho["capitulos"]
    ]


def puerta(almacen: Almacen, id_obra: str, numero: int, esquemas: Esquemas) -> dict[str, Any]:
    """Pasa los cuatro validadores sobre lo que ve la version (RF-146, RF-147).

    No guarda nada: el resultado se deriva cada vez (RD-30). Una version que no
    existe es un `KeyError`.
    """
    version = almacen.leer_version(id_obra, numero)
    obra = almacen.leer_obra(id_obra)
    if version is None or obra is None:
        raise KeyError(f"la obra {id_obra} no tiene version {numero}")
    capitulos = int(obra.cuerpo.get("capitulos_objetivo", 1))
    textos = _textos_por_capitulo(almacen, id_obra, numero, capitulos)
    fallos = [
        *_esquema(almacen, id_obra, numero, esquemas),
        *_nombres(almacen, id_obra, numero, textos),
        *_longitud(textos),
        *_elementos_personalizados(almacen, id_obra, numero),
    ]
    return {
        "id_obra": id_obra,
        "version": numero,
        "terminada": version["terminada_en"] is not None,
        "pasa": not fallos,
        "fallos": fallos,
    }


def publicar(almacen: Almacen, id_obra: str, numero: int, esquemas: Esquemas) -> str:
    """El unico sitio por el que una version queda publicada (RF-116, D-43).

    Terminar no publica: esto es una orden. Primero, que la version exista y
    haya terminado; despues, la puerta. Si la puerta falla no se publica y se
    dice por que; rehacer es otra orden del editor (RF-146). Devuelve cuando
    quedo publicada.
    """
    version = almacen.leer_version(id_obra, numero)
    if version is None:
        raise KeyError(f"la obra {id_obra} no tiene version {numero}")
    if version["terminada_en"] is None:
        raise VersionNoAdmitida(
            f"la version {numero} de {id_obra} no ha terminado: no se publica"
        )
    resultado = puerta(almacen, id_obra, numero, esquemas)
    if not resultado["pasa"]:
        raise PuertaNoSuperada(resultado)
    return almacen.publicar_version(id_obra, numero)


def de_referencia(almacen: Almacen, id_obra: str) -> int:
    """La que se sirve sin pedir version: la publicada, y si no, la ultima (D-43)."""
    publicada = almacen.version_publicada(id_obra)
    return publicada if publicada is not None else almacen.version_en_curso(id_obra)
