"""Las versiones de la obra: rehacer desde un capitulo y publicar (SPEC1 4.12).

Aqui no se decide nada del dominio: que capitulos cambian lo dice la orden del
editor, y lo que ve cada version lo deduce el almacen de dos numeros por fila.
Lo que se decide aqui es el orden de las cosas y que publicar pase por un solo
sitio, que es donde esta la puerta de publicacion (SPEC1 4.15).
"""

import json
from collections.abc import Sequence
from typing import Any, Protocol

from novela import validadores
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import VersionNoAdmitida
from novela.nucleo import guion
from novela.nucleo.caminante import IndiceDeLaObra
from novela.nucleo.proyecciones import nombres_de_la_biblia
from novela.vocabularios import TAREA_DE_ROL


class Esquemas(Protocol):
    """De donde sale el `esquema.json` de cada tarea: el catalogo de `tareas/`,
    que `nucleo` no importa."""

    def esquema(self, tarea: str) -> str: ...


class Demostrador(Protocol):
    """Quien comprueba la cronologia con Lean (SPEC1 4.16): `novela.demostrador`.

    Devuelve `comprobacion` —`demostrada`, `fallida` o `sin_comprobacion`— y la
    lista de `fallos` de la cronologia, cada uno con su invariante, su suceso,
    su capitulo, su detalle y su evidencia.
    """

    def comprobar(self, sucesos: Sequence[dict[str, Any]]) -> dict[str, Any]: ...


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


def sucesos_de_la_cronologia(
    almacen: Almacen, id_obra: str, numero: int
) -> list[dict[str, Any]]:
    """Lo que se vuelca a Lean: la cronologia de la version y quien muere (RF-150).

    La vista de RF-86 no dice el sujeto de cada `EventoEstado`; para el suceso
    `muere` se lee de su cuerpo, tal como lo escribio el Contable. Se copia, no
    se interpreta.

    Un cambio del lector deja la misma ficha con dos `id`: el viejo en los
    capitulos compartidos y el nuevo en los reescritos. Presentes, lugar y quien
    muere se llevan a la ficha vigente por `sustituye` (RF-177), para que Lean
    no los tome por dos personas o dos lugares.
    """
    sustituidas = almacen.fichas_sustituidas(id_obra, numero)

    def vigente(identificador: Any) -> Any:
        vistos: set[str] = set()
        while isinstance(identificador, str) and identificador in sustituidas:
            if identificador in vistos:
                break
            vistos.add(identificador)
            identificador = sustituidas[identificador]
        return identificador

    muertes = {
        evento.id: evento.cuerpo.get("sujeto")
        for evento in almacen.listar("EventoEstado", id_obra, version=numero)
        if evento.cuerpo.get("tipo_de_evento") == "muere"
    }
    return [
        suceso
        | {
            "lugar": vigente(suceso.get("lugar")),
            "presentes": [
                presente | {"id": vigente(presente.get("id"))}
                for presente in suceso.get("presentes") or []
            ],
            "muere": vigente(muertes.get(suceso["id"])),
        }
        for suceso in almacen.cronologia(id_obra, version=numero)
    ]


def _cronologia(
    almacen: Almacen, id_obra: str, numero: int, demostrador: Demostrador | None
) -> tuple[str, list[dict[str, Any]]]:
    """RF-152: la cronologia, demostrada por Lean o dicho que no se comprobo."""
    if demostrador is None:
        return "sin_comprobacion", []
    resultado = demostrador.comprobar(sucesos_de_la_cronologia(almacen, id_obra, numero))
    fallos = [
        _fallo("cronologia", fallo["capitulo"], fallo["detalle"]) | {"formal": fallo}
        for fallo in resultado["fallos"]
    ]
    return str(resultado["comprobacion"]), fallos


def puerta(
    almacen: Almacen,
    id_obra: str,
    numero: int,
    esquemas: Esquemas,
    demostrador: Demostrador | None = None,
) -> dict[str, Any]:
    """Pasa los validadores sobre lo que ve la version (RF-146, RF-147, RF-152).

    Los cuatro programaticos y, con `demostrador`, la cronologia en Lean. Sin
    Lean en la maquina la cronologia no se comprueba y el resultado lo dice en
    `comprobacion_formal`, pero eso no hace fallar la puerta (D-61). No guarda
    nada: el resultado se deriva cada vez (RD-30). Una version que no existe es
    un `KeyError`.
    """
    version = almacen.leer_version(id_obra, numero)
    obra = almacen.leer_obra(id_obra)
    if version is None or obra is None:
        raise KeyError(f"la obra {id_obra} no tiene version {numero}")
    capitulos = int(obra.cuerpo.get("capitulos_objetivo", 1))
    textos = _textos_por_capitulo(almacen, id_obra, numero, capitulos)
    comprobacion, de_la_cronologia = _cronologia(almacen, id_obra, numero, demostrador)
    fallos = [
        *_esquema(almacen, id_obra, numero, esquemas),
        *_nombres(almacen, id_obra, numero, textos),
        *_longitud(textos),
        *_elementos_personalizados(almacen, id_obra, numero),
        *de_la_cronologia,
    ]
    return {
        "id_obra": id_obra,
        "version": numero,
        "terminada": version["terminada_en"] is not None,
        "pasa": not fallos,
        "comprobacion_formal": comprobacion,
        "fallos": fallos,
    }


# Que dimension de calidad toca cada invariante de la cronologia (RF-154).
_DIMENSION_DEL_INVARIANTE = {
    "orden_temporal": "coherencia_temporal",
    "edad_coherente": "coherencia_temporal",
    "formato": "coherencia_temporal",
    "un_solo_lugar": "continuidad_de_estado",
    "no_reaparece": "continuidad_de_estado",
}


def _de_la_cronologia(critica: Artefacto) -> tuple[Any, Any] | None:
    detectada = critica.cuerpo.get("detectada_por") or {}
    if detectada.get("validador") != "cronologia":
        return None
    return critica.cuerpo.get("objeto"), detectada.get("invariante")


def _criticas_de_la_cronologia(almacen: Almacen, resultado: dict[str, Any]) -> list[str]:
    """RF-154: cada fallo de la cronologia con suceso vuelve como `Critica`.

    La escribe el backend, como la de un artefacto malformado (RF-23): ningun
    agente valida su propia salida. Una sola por suceso e invariante mientras
    siga abierta: volver a pedir la publicacion no la repite (D-63).
    """
    id_obra, numero = resultado["id_obra"], resultado["version"]
    abiertas = {
        _de_la_cronologia(critica)
        for critica in almacen.listar_criticas_abiertas(id_obra, version=numero)
    }
    nuevas = []
    for fallo in resultado["fallos"]:
        formal = fallo.get("formal")
        if not formal or not formal.get("suceso"):
            continue
        clave = (formal["suceso"], formal["invariante"])
        if clave in abiertas:
            continue
        abiertas.add(clave)
        capitulo = formal.get("capitulo")
        nuevas.append(
            Artefacto(
                tipo="Critica",
                cuerpo={
                    "objeto": formal["suceso"],
                    "evidencia": formal["detalle"],
                    "salida_de_lean": formal["evidencia"],
                    "accion_sugerida": (
                        f"rehacer desde el capitulo {capitulo} para que la cronologia no "
                        "se contradiga"
                        if capitulo
                        else "revisar el suceso del mundo para que la cronologia no se "
                        "contradiga"
                    ),
                    "detectada_por": {
                        "rol": None,
                        "tarea": None,
                        "validador": "cronologia",
                        "invariante": formal["invariante"],
                    },
                },
                id_obra=id_obra,
                capitulo=capitulo,
                dimension=_DIMENSION_DEL_INVARIANTE.get(formal["invariante"]),
                severidad="bloqueante",
                estado="abierta",
                version_de_obra=numero,
            )
        )
    return [almacen.guardar_critica(critica) for critica in nuevas]


def publicar(
    almacen: Almacen,
    id_obra: str,
    numero: int,
    esquemas: Esquemas,
    demostrador: Demostrador | None = None,
) -> tuple[str, str]:
    """El unico sitio por el que una version queda publicada (RF-116, D-43).

    Terminar no publica: esto es una orden. Primero, que la version exista y
    haya terminado; despues, la puerta. Si la puerta falla no se publica y se
    dice por que; rehacer es otra orden del editor (RF-146). Si lo que falla es
    la cronologia, el fallo vuelve ademas como `Critica` (RF-154). Devuelve
    cuando quedo publicada y como quedo la comprobacion formal (RF-155).
    """
    version = almacen.leer_version(id_obra, numero)
    if version is None:
        raise KeyError(f"la obra {id_obra} no tiene version {numero}")
    if version["terminada_en"] is None:
        raise VersionNoAdmitida(
            f"la version {numero} de {id_obra} no ha terminado: no se publica"
        )
    resultado = puerta(almacen, id_obra, numero, esquemas, demostrador)
    if not resultado["pasa"]:
        _criticas_de_la_cronologia(almacen, resultado)
        raise PuertaNoSuperada(resultado)
    return almacen.publicar_version(id_obra, numero), resultado["comprobacion_formal"]


def situacion(almacen: Almacen, id_obra: str) -> str:
    """Donde esta la obra, de `SITUACION_DE_LA_OBRA` (SPEC1 RF-205).

    Se calcula aqui y no en la interfaz porque sale de tres hechos que solo el
    backend tiene juntos, y el orden en que se miran es parte de la regla (D-89):
    una obra detenida lo esta aunque su version no haya terminado, y una
    publicada a la que se le pide rehacer vuelve a estar en produccion.
    """
    if almacen.esta_detenida(id_obra):
        return "detenida"
    en_curso = almacen.version_en_curso(id_obra)
    version = almacen.leer_version(id_obra, en_curso)
    if version is None or version["terminada_en"] is None:
        return "en_produccion"
    if almacen.version_publicada(id_obra) == en_curso:
        return "publicada"
    return "terminada"


def de_referencia(almacen: Almacen, id_obra: str) -> int:
    """La que se sirve sin pedir version: la publicada, y si no, la ultima (D-43)."""
    publicada = almacen.version_publicada(id_obra)
    return publicada if publicada is not None else almacen.version_en_curso(id_obra)
