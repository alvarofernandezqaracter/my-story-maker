# §20 Credenciales de las trazas y §12 credencial de la API: las dos viven en el
# entorno y no en config.json, porque ese fichero se versiona. Esto lee el .env
# de la raiz y lo mete en el entorno del proceso.
#
# Es un lector minimo a proposito: el repo no instala nada en modo simulado y
# python-dotenv seria la primera dependencia para veinte lineas. Lo que no
# soporta -comillas raras, valores multilinea, export- no hace falta aqui.
import os
from pathlib import Path

FICHERO = '.env'


def leer_env(ruta=FICHERO):
    """Devuelve el .env como diccionario. Si no existe, diccionario vacio."""
    fichero = Path(str(ruta))
    if not fichero.exists():
        return {}

    pares = {}
    for linea in fichero.read_text(encoding='utf-8').splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith('#') or '=' not in limpia:
            continue
        clave, _, valor = limpia.partition('=')
        valor = valor.strip()
        # Las comillas envuelven el valor, no forman parte de el.
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
            valor = valor[1:-1]
        pares[clave.strip()] = valor
    return pares


def cargar_entorno(ruta=FICHERO):
    """Mete el .env en os.environ sin pisar lo que ya haya.

    El entorno real gana siempre: quien exporta una variable a mano lo hace
    para esta ejecucion y el fichero no tiene por que contradecirle.
    """
    puestas = []
    for clave, valor in leer_env(ruta).items():
        if clave not in os.environ:
            os.environ[clave] = valor
            puestas.append(clave)
    return puestas
