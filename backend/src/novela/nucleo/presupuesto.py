"""El presupuesto de contexto: que cabe a la vez y que hay que partir.

El techo son 100 000 tokens de entrada **simultaneos** y **cuenta solo lo que
entra**: lo que los agentes devuelven se paga en coste y no ocupa techo, asi
que en el reparto de una tanda no se reserva nada para las respuestas. El
agente que termina libera su parte, de modo que una cadena secuencial larga no
agota el techo por larga que sea. Lo que lo agota es abrir demasiados frentes
en paralelo.

Dos reglas mas, y ninguna es opinable. La anchura de una tanda se calcula, no
se elige. Y si una proyeccion no cabe en el tope de su rol, **se parte la
unidad** —capitulo, escena, parrafo— en vez de recortar la proyeccion:
recortarla fabrica falsos negativos, porque el agente deja de ver justamente lo
que tenia que comparar.
"""

from collections.abc import Sequence

from novela.ajustes import (
    CARACTERES_POR_TOKEN_ESTIMADOS,
    COSTE_FIJO_DEL_SUBAGENTE_EN_TOKENS,
    K_POR_ROL,
    TECHO_DE_CONTEXTO_CONCURRENTE,
    tokens_repartibles,
)
from novela.nucleo.guion import Encargo

# De mayor a menor. Partir es bajar un escalon de esta escalera.
ESCALERA_DE_UNIDADES: tuple[str, ...] = ("obra", "capitulo", "escena", "parrafo")


class NoCabeNiPartiendo(Exception):
    """La proyeccion no entra en el tope del rol ni en la unidad mas pequena."""


def estimar_tokens(texto: str) -> int:
    """Cuenta previa de la ventana, antes de mandarla.

    Es una estimacion, no la cuenta del proveedor: con que se cuentan los
    tokens antes de enviar sigue siendo una decision abierta (SPEC1 12). La
    medida exacta la devuelve el subagente al terminar y queda en la `Traza`,
    y es contra ella contra la que se calibra este factor.
    """
    return int(len(texto) / CARACTERES_POR_TOKEN_ESTIMADOS) + 1


def coste_de_abrir(tope_del_rol: int) -> int:
    """Lo que ocupa en el techo un agente abierto de ese rol.

    No es solo su proyeccion: un subagente de Claude Code arrastra su propio
    sistema y sus definiciones de herramienta antes de que entre nada nuestro,
    y eso son tokens de entrada como cualquier otro.
    """
    return tope_del_rol + COSTE_FIJO_DEL_SUBAGENTE_EN_TOKENS


def coste_de_abrir_encargo(encargo: Encargo) -> int:
    """Lo que ocupa en el techo un encargo abierto, en el peor caso.

    Si su paso lleva hooks, la vuelta de correccion vuelve a leer el encargo mas
    la respuesta anterior y el motivo: no arranca en frio, y lo que anade es
    entrada. Su reserva se cuenta aqui (SPEC1 RF-128).
    """
    reserva = encargo.reserva_de_la_vuelta if encargo.ganchos else 0
    return coste_de_abrir(encargo.tope_de_ventana) + reserva


def anchura_de_tanda(encargos: Sequence[Encargo]) -> int:
    """`80 000 / lo que cuesta abrir el encargo mas caro`, redondeado a la baja."""
    if not encargos:
        return 0
    mas_caro = max(coste_de_abrir_encargo(encargo) for encargo in encargos)
    return max(1, tokens_repartibles() // mas_caro)


def repartir_en_tandas(encargos: Sequence[Encargo]) -> list[list[Encargo]]:
    """Parte la lista en tandas sucesivas. Se espera a que cierre una antes de
    abrir la siguiente: nunca en abanico libre."""
    anchura = anchura_de_tanda(encargos)
    if anchura == 0:
        return []
    return [list(encargos[i : i + anchura]) for i in range(0, len(encargos), anchura)]


def cabe_en_la_ventana(rol_tope: int, tokens: int) -> bool:
    return tokens <= rol_tope


def partir_unidad(unidad: str) -> str:
    """De capitulo a escena, de escena a parrafo. La proyeccion no se toca."""
    if unidad not in ESCALERA_DE_UNIDADES:
        raise ValueError(f"{unidad!r} no es una unidad del sistema")
    posicion = ESCALERA_DE_UNIDADES.index(unidad)
    if posicion == len(ESCALERA_DE_UNIDADES) - 1:
        raise NoCabeNiPartiendo(
            f"la proyeccion no cabe ni en la unidad mas pequena ({unidad})"
        )
    return ESCALERA_DE_UNIDADES[posicion + 1]


def k_que_cabe(
    rol: str, tokens_ya_ocupados: int, tope_del_rol: int, tokens_por_fragmento: int
) -> int:
    """Lo recuperado paga en el tope de su rol: si no cabe, baja `k`."""
    k_declarada = K_POR_ROL.get(rol, 0)
    if k_declarada == 0 or tokens_por_fragmento <= 0:
        return 0
    hueco = tope_del_rol - tokens_ya_ocupados
    if hueco <= 0:
        return 0
    return max(0, min(k_declarada, hueco // tokens_por_fragmento))


def pico_admisible(tokens_abiertos: int, tokens_del_encargo: int) -> bool:
    """Si abrir este encargo mantiene el techo. Cuenta solo la entrada, y
    cuenta tambien lo que el subagente pone de su parte."""
    return (
        tokens_abiertos + coste_de_abrir(tokens_del_encargo)
        <= TECHO_DE_CONTEXTO_CONCURRENTE
    )
