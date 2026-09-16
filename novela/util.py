# Utilidades numericas compartidas. Viven aparte porque las usan el gate (§8),
# VD-08 (§9) y la CLI (§18), y no pertenecen a ninguno de los tres.
from decimal import Decimal, ROUND_HALF_UP


def redondear(valor, decimales=2):
    """Redondea a medio arriba.

    Python redondea a medio par y eso, en los pocos empates exactos que dan los
    flotantes, cambia el texto de un mensaje. Aqui se fija el criterio para que
    las cifras que ve el usuario no dependan de ese detalle.
    """
    paso = Decimal(1).scaleb(-decimales)
    return float(Decimal(repr(float(valor))).quantize(paso, rounding=ROUND_HALF_UP))


def numero_corto(valor):
    """4.0 se imprime 4, y 3.67 se imprime 3.67.

    Lo que el harness escribe son umbrales y notas, no medidas: un ".0" colgando
    solo estorba al leerlo.
    """
    return int(valor) if float(valor).is_integer() else valor
