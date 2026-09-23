"""Un unico fichero de ajustes: lo que hoy es configuracion.

Lo que esta aqui se cambia sin tocar codigo. Lo que no esta aqui es invariante
y cambiarlo exige una spec. Los topes de ventana se copian tal cual de
`architecture.md` 3: son una asignacion de diseno, no una medida, y la `Traza`
existe en parte para revisarlos.
"""

import os
from pathlib import Path

from novela.vocabularios import ROLES

# --- Donde vive el almacen -------------------------------------------------

RUTA_DE_LA_BASE: Path = Path(
    os.environ.get("NOVELA_BASE_DE_DATOS", Path.cwd() / "novela.sqlite3")
)

# Tiempo que una conexion espera a que el escritor suelte la base, en milisegundos.
ESPERA_POR_BLOQUEO_MS: int = 5_000

# --- Presupuesto de contexto (architecture.md 3) ---------------------------

# El techo es de concurrencia y cuenta solo la entrada: la suma de las ventanas
# abiertas a la vez. Lo que los agentes devuelven se paga en coste y no ocupa
# techo, asi que en el reparto de una tanda no se reserva nada para respuestas.
TECHO_DE_CONTEXTO_CONCURRENTE: int = 100_000

# Se reserva el 20 % para lo que no se puede prever; el resto es lo repartible.
MARGEN_DEL_TECHO: float = 0.20

TOPE_DE_VENTANA_POR_ROL: dict[str, int] = {
    "arquitecto_de_arcos": 25_000,
    "planificador": 20_000,
    "revisor": 20_000,
    "constructor_de_mundo": 15_000,
    "contable_de_estado": 12_000,
    "archivero": 12_000,
    "redactor": 12_000,
    "documentalista": 8_000,
    "verificador_de_continuidad": 8_000,
    "editor_de_estilo": 8_000,
    "juez_de_rubrica": 6_000,
}

# --- Recuperacion por parecido ---------------------------------------------

# Cuantos fragmentos pide cada rol y cuanto puede ocupar lo recuperado. Lo
# recuperado se descuenta del tope de ventana del que consulta, no se suma
# aparte: si no cabe, baja `k`. Los roles que no consultan por parecido tienen
# `k = 0` por diseno, no por olvido (RF-67).
K_POR_ROL: dict[str, int] = {
    "documentalista": 8,
    "editor_de_estilo": 6,
    "planificador": 6,
    "constructor_de_mundo": 0,
    "arquitecto_de_arcos": 0,
    "redactor": 0,
    "contable_de_estado": 0,
    "verificador_de_continuidad": 0,
    "juez_de_rubrica": 0,
    "revisor": 0,
    "archivero": 0,
}

TOPE_DE_TOKENS_RECUPERADOS_POR_ROL: dict[str, int] = {
    "documentalista": 2_500,
    "editor_de_estilo": 1_500,
    "planificador": 3_000,
}

# Valor de partida declarado, pendiente de calibrar contra trazas (SPEC1 12).
TAMANO_DE_FRAGMENTO_EN_CARACTERES: int = 900
SOLAPE_ENTRE_FRAGMENTOS_EN_CARACTERES: int = 150

# Las huellas se calculan en la propia maquina (D-10). Cambiar de modelo obliga
# a reindexar la obra entera: dos modelos conviviendo en el indice son defecto.
MODELO_DE_HUELLAS: str = "intfloat/multilingual-e5-small"
DIMENSIONES_DE_LA_HUELLA: int = 384

# --- Bucle de control de calidad (architecture.md 5) -----------------------

TOPE_DE_REVISIONES_POR_BORRADOR: int = 2
TOPE_DE_REGENERACIONES_POR_ESCENA: int = 2

# --- Ejecucion de tareas ---------------------------------------------------

# Las tareas las ejecutan subagentes de Claude Code (D-08). El backend no llama
# a ninguna API de modelo ni gestiona claves.
MODELO_DE_LOS_SUBAGENTES: str = "claude-haiku-4-5-20251001"
TOPE_DE_REINTENTOS_POR_TAREA: int = 2
ESPERA_MAXIMA_POR_TAREA_EN_SEGUNDOS: int = 900

# --- Cadencia del guion ----------------------------------------------------

# Cada cuantos capitulos entra `auditar`. Cero significa solo al cierre de la
# obra, que es el valor de partida: auditar antes de tener resumenes que
# comparar no mide nada.
CADA_CUANTOS_CAPITULOS_SE_AUDITA: int = 0

# v1 declara el tope del unico material que sigue entrando entero y avisa al
# alcanzarlo, pero no compacta (SPEC1 11).
TOPE_DE_LOS_RESUMENES_DE_CAPITULO_EN_TOKENS: int = 6_000

# Cuantos parrafos del capitulo anterior entran en crudo como cola de
# continuidad local. Es corta y de tamano fijo: es la unica prosa cerrada que
# se relee.
PARRAFOS_DE_CONTINUIDAD_LOCAL: int = 3


def tope_de_ventana(rol: str) -> int:
    """Tope de ventana del rol. Un rol sin tope declarado es un defecto."""
    if rol not in TOPE_DE_VENTANA_POR_ROL:
        raise KeyError(f"El rol {rol!r} no tiene tope de ventana declarado")
    return TOPE_DE_VENTANA_POR_ROL[rol]


def tokens_repartibles() -> int:
    """Lo que queda del techo una vez apartado el margen: 80 000 utiles."""
    return int(TECHO_DE_CONTEXTO_CONCURRENTE * (1 - MARGEN_DEL_TECHO))


assert set(TOPE_DE_VENTANA_POR_ROL) == set(ROLES), "Falta el tope de ventana de algun rol"
assert set(K_POR_ROL) == set(ROLES), "Falta la `k` de algun rol"
