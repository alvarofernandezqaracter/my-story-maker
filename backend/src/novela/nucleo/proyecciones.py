"""El ensamblador de contexto: que ve cada rol y que no ve.

La pregunta operativa no es que sabe el sistema, sino que proyeccion recibe
cada agente en cada paso. Aqui se arma esa ventana y se coteja con la
proyeccion que el paso o el contrato declararon, en las dos direcciones:
completa, porque si falta una pieza el verificador no falla sino que contesta
que el predicado se cumple; y minima, porque el material de sobra es lo que
invita a opinar en vez de comprobar.

**La linea que no se cruza:** el ensamblador lee referencias —el `id` de un
personaje en el elenco de una escena— y nunca contenido. Elegir que artefactos
entran en la ventana es ensamblar; interpretar lo que dicen por dentro seria
decidir del dominio, y eso es trabajo de los once roles.

Toda tarea arranca en frio: la ventana se construye desde cero a partir de los
artefactos escritos. Eso es lo que hace el techo verificable antes de gastar.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dcfield
from typing import Any, Protocol

from novela.ajustes import PARRAFOS_DE_CONTINUIDAD_LOCAL
from novela.almacen import Almacen, Artefacto
from novela.nucleo.guion import Encargo
from novela.nucleo.presupuesto import estimar_tokens
from novela.vocabularios import (
    HECHOS_DE_LA_BIBLIA,
    TIPO_DE_EVENTO_ESTADO,
    TIPOS_DE_LA_CAPA_MUNDO,
)

Material = Any
Filas = list[dict[str, Any]]


class Indice(Protocol):
    """Lo que el ensamblador necesita de la recuperacion por parecido."""

    def recuperar(self, id_obra: str, coleccion: str, consulta: str, rol: str) -> Filas: ...


class ProyeccionIncompleta(Exception):
    """Falta una pieza declarada. La tarea no sale: parar cuesta una vuelta y
    mandar un verificador ciego cuesta el resto de la obra."""


class ProyeccionConMaterialDeSobra(Exception):
    """Va en la ventana algo que el contrato no declaro."""


@dataclass
class Peticion:
    """Todo lo que un material necesita para traerse a si mismo."""

    almacen: Almacen
    encargo: Encargo
    contrato: dict[str, Any] | None = None
    indice: Indice | None = None
    recuperaciones: list[dict[str, Any]] = dcfield(default_factory=list)

    @property
    def id_obra(self) -> str:
        return self.encargo.id_obra

    @property
    def capitulo(self) -> int | None:
        return self.encargo.capitulo

    @property
    def escena(self) -> str | None:
        return self.encargo.escena


@dataclass
class Ventana:
    """Lo que se le manda a un agente, ya medido.

    `recuperaciones` guarda que se pidio al indice y que devolvio, porque sin
    eso OBJ-08 no se puede medir.
    """

    materiales: dict[str, Material]
    texto: str
    tokens: int
    recuperaciones: list[dict[str, Any]] = dcfield(default_factory=list)
    # Lo que el hook `policy` busca en lo entregado (SPEC1 RF-124, 4.14): los
    # vetos del comprador y la lista global. **No entran en el texto de la
    # ventana**: viajan aparte, hasta el hook, y al agente solo le llega lo que
    # encontro en su propio texto.
    vetos: tuple[str, ...] = ()
    vetos_globales: tuple[str, ...] = ()
    # Los nombres de la biblia, para que `validar_capitulo` compruebe que se
    # escriben tal cual (SPEC1 RF-145). Tampoco entran en el texto de la ventana.
    nombres: tuple[str, ...] = ()


Constructor = Callable[[Peticion], Material]


def _cuerpos(artefactos: list[Artefacto]) -> Filas:
    """El cuerpo integro mas el envoltorio minimo para saber que se mira."""
    filas: Filas = []
    for artefacto in artefactos:
        envoltorio: dict[str, Any] = {"id": artefacto.id, "tipo": artefacto.tipo}
        if artefacto.capitulo is not None:
            envoltorio["capitulo"] = artefacto.capitulo
        if artefacto.escena is not None:
            envoltorio["escena"] = artefacto.escena
        filas.append(artefacto.cuerpo | envoltorio)
    return filas


def _la_escena(p: Peticion) -> Artefacto | None:
    return p.almacen.leer("Escena", p.escena) if p.escena else None


# --- Los materiales, uno por uno -------------------------------------------


def _canon(p: Peticion) -> Filas:
    """Fichas del mundo. Se traen por `id`, no por parecido: cambiar algo
    seguro por algo probable no gana nada.

    El `Recuerdo` queda fuera aunque sea de la capa Mundo: no es una ficha, es
    la materia prima con la que el Constructor escribe fichas, y tiene material
    propio para los dos roles que lo necesitan (RF-16).
    """
    fichas: Filas = []
    for tipo in TIPOS_DE_LA_CAPA_MUNDO:
        if tipo == "Recuerdo":
            continue
        fichas += _cuerpos(p.almacen.listar(tipo, p.id_obra))
    return fichas


def _indice_de_la_biblia(p: Peticion) -> Filas:
    """Una linea por hecho: `id`, tipo, nombre y licencia, y nada mas (RF-82).

    Es con lo que el Archivero anota que hechos nombra el capitulo cerrado. No
    es el canon: de la ficha se copian cuatro campos sin interpretarlos, y los
    atributos del mundo se quedan fuera.
    """
    filas: Filas = []
    for tipo in HECHOS_DE_LA_BIBLIA:
        for ficha in p.almacen.listar(tipo, p.id_obra):
            filas.append(
                {
                    "id": ficha.id,
                    "tipo": ficha.tipo,
                    "nombre": ficha.cuerpo.get("nombre") or ficha.cuerpo.get("descripcion"),
                    "licencia": ficha.cuerpo.get("licencia"),
                }
            )
    return filas


def _estado_en_n(p: Peticion) -> dict[str, Any]:
    return p.almacen.estado_en(p.id_obra, p.capitulo or 0) or {}


def _estado_en_n_menos_1(p: Peticion) -> dict[str, Any]:
    return p.almacen.estado_en(p.id_obra, (p.capitulo or 1) - 1) or {}


def _compromisos_abiertos(p: Peticion) -> Filas:
    return _cuerpos(p.almacen.listar("Compromiso", p.id_obra, estado="abierto"))


def _cola_de_compromisos(p: Peticion) -> Filas:
    return _cuerpos(p.almacen.listar("Compromiso", p.id_obra))


def _continuidad_local(p: Peticion) -> Filas:
    """Cola literal de los ultimos parrafos del capitulo anterior. Es la unica
    prosa cerrada que se relee, y por eso es corta y de tamano fijo."""
    anterior = (p.capitulo or 1) - 1
    if anterior < 1:
        return []
    parrafos = p.almacen.listar("Parrafo", p.id_obra, capitulo=anterior, orden="orden")
    return _cuerpos(parrafos[-PARRAFOS_DE_CONTINUIDAD_LOCAL:])


def _contrato_de_escena(p: Peticion) -> dict[str, Any]:
    escena = _la_escena(p)
    return (escena.cuerpo | {"id": escena.id, "tipo": "Escena"}) if escena else {}


def _voces_del_elenco(p: Peticion) -> Filas:
    """Se siguen las referencias del contrato de escena, no su contenido."""
    escena = _la_escena(p)
    if escena is None:
        return []
    fichas: Filas = []
    for identificador in escena.cuerpo.get("elenco_presente") or []:
        if not isinstance(identificador, str):
            continue
        ficha = p.almacen.leer("Personaje", identificador)
        if ficha is not None:
            fichas.append(ficha.cuerpo | {"id": ficha.id, "tipo": "Personaje"})
    return fichas


def _texto_producido(p: Peticion) -> Filas:
    if p.escena:
        vigente = p.almacen.borrador_vigente(p.id_obra, p.escena)
        return _cuerpos([vigente]) if vigente else []
    borradores = p.almacen.listar("Borrador", p.id_obra, capitulo=p.capitulo)
    return _cuerpos([b for b in borradores if b.estado != "descartado"])


def _texto_aceptado_del_capitulo(p: Peticion) -> Filas:
    borradores = p.almacen.listar("Borrador", p.id_obra, capitulo=p.capitulo)
    return _cuerpos([b for b in borradores if b.estado == "aceptado"])


def _criticas_a_atender(p: Peticion) -> Filas:
    """Solo las de esta unidad: el Revisor no ve criticas de otras unidades."""
    return _cuerpos(p.almacen.listar_criticas_abiertas(p.id_obra, escena=p.escena))


def _la_obra(p: Peticion) -> dict[str, Any]:
    """El brief sin el destinatario: quien lo necesita lo pide por su nombre.

    Colarlo aqui dentro lo haria llegar a todo rol que pida la obra y la
    premisa, que es justo lo que RF-16 prohibe.
    """
    obra = p.almacen.leer_obra(p.id_obra)
    if obra is None:
        return {}
    return {clave: valor for clave, valor in obra.cuerpo.items() if clave != "destinatario"}


def _destinatario(p: Peticion) -> dict[str, Any]:
    """A quien va dedicada la obra. Vacio si no va dedicada a nadie."""
    obra = p.almacen.leer_obra(p.id_obra)
    if obra is None:
        return {}
    destinatario = obra.cuerpo.get("destinatario")
    return destinatario if isinstance(destinatario, dict) else {}


def vetos_del_encargo(almacen: Almacen, encargo: Encargo) -> tuple[str, ...]:
    """Las palabras o temas que el comprador veto en el brief (SPEC1 RF-130).

    Se leen del cuerpo de la `Obra`, donde ya estan: no se copian (D-50). Si
    cada uno es palabra o tema lo decide el hook por su forma.
    """
    if "policy" not in encargo.ganchos:
        return ()
    obra = almacen.leer_obra(encargo.id_obra)
    destinatario = obra.cuerpo.get("destinatario") if obra is not None else None
    vetos = destinatario.get("vetos") if isinstance(destinatario, dict) else None
    if not isinstance(vetos, list):
        return ()
    return tuple(veto for veto in vetos if isinstance(veto, str) and veto)


def vetos_globales_del_encargo(almacen: Almacen, encargo: Encargo) -> tuple[str, ...]:
    """La lista global de la instalacion, para todo encargo con `policy` (RF-131)."""
    if "policy" not in encargo.ganchos:
        return ()
    return tuple(almacen.terminos_vetados_globales())

# Los hechos de la biblia que tienen nombre propio: el `Evento` se conoce por su
# descripcion, y una descripcion no es un nombre que haya que escribir tal cual.
TIPOS_CON_NOMBRE: tuple[str, ...] = ("Personaje", "Lugar", "Objeto", "Faccion")


def nombres_de_la_biblia(
    almacen: Almacen, id_obra: str, *, version: int | None = None
) -> tuple[str, ...]:
    """El nombre del destinatario y el `nombre` y los `tratamientos` de cada
    ficha con nombre, tal como estan escritos (SPEC1 RF-142).

    Copia campos sin interpretarlos: es proyeccion, no decision.
    """
    nombres: list[str] = []
    obra = almacen.leer_obra(id_obra)
    destinatario = obra.cuerpo.get("destinatario") if obra is not None else None
    if isinstance(destinatario, dict) and isinstance(destinatario.get("nombre"), str):
        nombres.append(destinatario["nombre"])
    for tipo in TIPOS_CON_NOMBRE:
        for ficha in almacen.listar(tipo, id_obra, version=version):
            candidatos = [ficha.cuerpo.get("nombre")]
            tratamientos = ficha.cuerpo.get("tratamientos")
            if isinstance(tratamientos, list):
                candidatos += tratamientos
            for nombre in candidatos:
                if isinstance(nombre, str) and nombre and nombre not in nombres:
                    nombres.append(nombre)
    return tuple(nombres)


def nombres_del_encargo(almacen: Almacen, encargo: Encargo) -> tuple[str, ...]:
    """Lo que el hook `validar_capitulo` necesita para mirar los nombres."""
    if "validar_capitulo" not in encargo.ganchos:
        return ()
    return nombres_de_la_biblia(almacen, encargo.id_obra)


def _recuerdos_del_destinatario(p: Peticion) -> Filas:
    """Lo que el editor aporto de su vida, como dato delimitado (RD-16)."""
    return _cuerpos(p.almacen.listar("Recuerdo", p.id_obra))


def _resumenes_de_capitulos(p: Peticion) -> Filas:
    return _cuerpos(p.almacen.listar("ResumenCapitulo", p.id_obra, orden="capitulo"))


def _fuentes_recogidas(p: Peticion) -> Filas:
    return _cuerpos(p.almacen.listar("Fuente", p.id_obra))


def _registro_linguistico(p: Peticion) -> Filas:
    """Lista corta y del capitulo, no la lista global: un agente revisa bien
    veinte terminos, no mil."""
    return _cuerpos(p.almacen.listar("RegistroLinguistico", p.id_obra))


def _afirmaciones_pendientes_de_respaldo(p: Peticion) -> Filas:
    return _cuerpos(
        p.almacen.listar(
            "Critica",
            p.id_obra,
            escena=p.escena,
            estado="abierta",
            dimension="cobertura_documental",
        )
    )


def _plan_del_capitulo(p: Peticion) -> Filas:
    return _cuerpos(p.almacen.listar("Plan", p.id_obra, capitulo=p.capitulo))


def _funcion_estructural_de_las_escenas(p: Peticion) -> Filas:
    """Los contratos de todas las escenas en orden.

    Es uno de los dos materiales a los que se les permite crecer con la obra, y
    lo lee un solo rol: el Arquitecto de arcos, que audita ausencias, y una
    ausencia es exactamente lo que una muestra no devuelve.
    """
    return _cuerpos(p.almacen.listar("Escena", p.id_obra, orden="capitulo, orden"))


def _log_de_estado(p: Peticion) -> Filas:
    """El log entero, y solo para auditar.

    La regla del tamano prohibe que esto entre en una ventana de la cadencia del
    capitulo: aqui entra porque `auditar` va fuera del guion, en solitario y
    cada N capitulos, y porque su predicado habla justamente del reparto de las
    revelaciones a lo largo de toda la obra.
    """
    return _cuerpos(p.almacen.listar("EventoEstado", p.id_obra, orden="capitulo"))


def _decisiones(p: Peticion) -> Filas:
    return _cuerpos(p.almacen.listar("Decision", p.id_obra))


def _vocabulario_de_eventos(p: Peticion) -> list[str]:
    return list(TIPO_DE_EVENTO_ESTADO)


def _contrato_de_verificacion(p: Peticion) -> dict[str, Any]:
    """El predicado, la proyeccion minima y la forma de la `Critica`."""
    return p.contrato or {"dimension": p.encargo.dimension}


def _recuperar(coleccion: str) -> Constructor:
    """Lo recuperado por parecido paga en el tope del rol que consulta."""

    def constructor(p: Peticion) -> Filas:
        if p.indice is None:
            return []
        consulta = p.escena or f"capitulo {p.capitulo}"
        fragmentos = p.indice.recuperar(p.id_obra, coleccion, consulta, p.encargo.rol)
        p.recuperaciones.append(
            {
                "consulta": consulta,
                "coleccion": coleccion,
                "k": len(fragmentos),
                "devueltos": [f.get("id") for f in fragmentos],
            }
        )
        return fragmentos

    return constructor


MATERIALES: dict[str, Constructor] = {
    "canon": _canon,
    "indice_de_la_biblia": _indice_de_la_biblia,
    "estado_en_n": _estado_en_n,
    "estado_en_n_menos_1": _estado_en_n_menos_1,
    "compromisos_abiertos": _compromisos_abiertos,
    "cola_de_compromisos": _cola_de_compromisos,
    "continuidad_local": _continuidad_local,
    "contrato_de_escena": _contrato_de_escena,
    "marco_de_la_escena": _contrato_de_escena,
    "voces_del_elenco": _voces_del_elenco,
    "texto_producido": _texto_producido,
    "borrador_vigente": _texto_producido,
    "texto_aceptado_del_capitulo": _texto_aceptado_del_capitulo,
    "criticas_a_atender": _criticas_a_atender,
    "arcos": _la_obra,
    "obra_y_premisa": _la_obra,
    "elenco_declarado": _la_obra,
    "destinatario": _destinatario,
    "recuerdos_del_destinatario": _recuerdos_del_destinatario,
    "resumenes_de_capitulos": _resumenes_de_capitulos,
    "fuentes_recogidas": _fuentes_recogidas,
    "registro_linguistico": _registro_linguistico,
    "lexico_vetado": _registro_linguistico,
    "afirmaciones_pendientes_de_respaldo": _afirmaciones_pendientes_de_respaldo,
    "vocabulario_de_eventos": _vocabulario_de_eventos,
    "plan_del_capitulo": _plan_del_capitulo,
    "funcion_estructural_de_las_escenas": _funcion_estructural_de_las_escenas,
    "log_de_estado": _log_de_estado,
    "decisiones": _decisiones,
    "contrato_de_verificacion": _contrato_de_verificacion,
    "documentacion": _recuperar("documental"),
    "ecos_de_la_obra": _recuperar("obra_prosa"),
    "ecos_del_registro": _recuperar("obra_prosa"),
    "registro_acumulado_de_estilo": _recuperar("obra_prosa"),
    "ecos_de_estructura": _recuperar("obra_estructura"),
}


def ensamblar(
    almacen: Almacen,
    encargo: Encargo,
    *,
    contrato: dict[str, Any] | None = None,
    indice: Indice | None = None,
    proyeccion_del_contrato: tuple[str, ...] = (),
) -> Ventana:
    """Arma la ventana del encargo y la coteja antes de que salga."""
    declarada = tuple(dict.fromkeys(encargo.proyeccion + proyeccion_del_contrato))
    peticion = Peticion(almacen=almacen, encargo=encargo, contrato=contrato, indice=indice)
    materiales: dict[str, Material] = {}
    for nombre in declarada:
        constructor = MATERIALES.get(nombre)
        if constructor is None:
            raise ProyeccionIncompleta(
                f"el material {nombre!r} esta declarado y nadie sabe traerlo"
            )
        materiales[nombre] = constructor(peticion)

    cotejar(materiales, declarada)
    texto = json.dumps(materiales, ensure_ascii=False, sort_keys=True)
    return Ventana(
        materiales=materiales,
        texto=texto,
        tokens=estimar_tokens(texto),
        recuperaciones=peticion.recuperaciones,
        vetos=vetos_del_encargo(almacen, encargo),
        vetos_globales=vetos_globales_del_encargo(almacen, encargo),
        nombres=nombres_del_encargo(almacen, encargo),
    )


def cotejar(materiales: dict[str, Material], declarada: tuple[str, ...]) -> None:
    """Compara la ventana con el contrato en las dos direcciones."""
    faltan = [nombre for nombre in declarada if nombre not in materiales]
    if faltan:
        raise ProyeccionIncompleta(f"la ventana sale sin: {', '.join(faltan)}")
    sobran = [nombre for nombre in materiales if nombre not in declarada]
    if sobran:
        raise ProyeccionConMaterialDeSobra(f"la ventana lleva de mas: {', '.join(sobran)}")
