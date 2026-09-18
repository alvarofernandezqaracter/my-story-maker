# §12 Configuracion. Un unico config.json en la raiz. Se carga al arrancar, se
# valida entero y se para si falta una clave o un valor cae fuera de rango: una
# errata en un umbral sale mas barata descubierta al arrancar.
#
# **Todo lo que hay aqui lo lee tambien el orquestador**, que no es codigo sino
# una sesion de Claude Code (§21): la skill imprime estos numeros y los obedece.
# Por eso un umbral escrito a mano en un prompt sigue siendo un bug aunque ya no
# nadie de este paquete lo lea.
import json
import math
import re

# Lo que Langfuse acepta como nombre de entorno (§20). Se valida aqui, al
# arrancar, por la misma razon que todo lo demas de este fichero: un entorno mal
# escrito se descubre tres capitulos despues, cuando las trazas no aparecen
# donde se las busca.
ENTORNO_DE_TRAZAS = re.compile(r'^(?!langfuse)[a-z0-9_\-]{1,40}$')

# Los modos de permiso con los que el lanzador de §19 puede arrancar una sesion.
# Se valida aqui por lo mismo: un modo mal escrito no se ve hasta que la sesion
# ya ha arrancado y se ha quedado parada sin nadie a quien preguntar.
PERMISOS_DE_CLAUDE = ('default', 'acceptEdits', 'bypassPermissions', 'plan')

class ErrorConfig(Exception):
    """config.json no sirve. Se para antes de hacer nada."""


def _entero(v):
    # Los booleanos de JSON son int en Python y aqui no cuelan como enteros.
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _fraccion(v):
    return _numero(v) and 0 < v < 1


# (clave, predicado, que se espera)
REGLAS = [
    ('gate.nota_minima', lambda v: _entero(v) and 1 <= v <= 5, 'entero entre 1 y 5'),
    ('gate.media_minima', lambda v: _numero(v) and 1 <= v <= 5, 'numero entre 1 y 5'),
    ('gate.max_intentos', lambda v: _entero(v) and v >= 1, 'entero >= 1'),
    ('contexto.tope_contexto', lambda v: _entero(v) and v > 0, 'entero > 0'),
    ('contexto.ventana_resumenes', lambda v: _entero(v) and v >= 0, 'entero >= 0'),
    ('contexto.palabras_enganche', lambda v: _entero(v) and v >= 0, 'entero >= 0'),
    ('interfaz.puerto', lambda v: _entero(v) and 1024 <= v <= 65535,
     'entero entre 1024 y 65535'),
    ('lanzador.comando', lambda v: isinstance(v, str) and bool(v.strip()),
     'el nombre o la ruta del CLI de Claude Code'),
    ('lanzador.permisos', lambda v: v in PERMISOS_DE_CLAUDE,
     'uno de ' + ', '.join(PERMISOS_DE_CLAUDE)),
    ('margenes.capitulos_min', lambda v: _numero(v) and 0 < v <= 1, 'numero en (0, 1]'),
    ('margenes.capitulos_max', lambda v: _numero(v) and v >= 1, 'numero >= 1'),
    ('margenes.palabras_aviso', _fraccion, 'fraccion en (0, 1)'),
    ('margenes.palabras_bloqueo', _fraccion, 'fraccion en (0, 1)'),
    ('margenes.parrafos_min', lambda v: _entero(v) and v >= 1, 'entero >= 1'),
    ('trazas.activas', lambda v: isinstance(v, bool), 'booleano'),
    ('trazas.texto', lambda v: isinstance(v, bool), 'booleano'),
    ('trazas.entorno', lambda v: isinstance(v, str) and bool(ENTORNO_DE_TRAZAS.match(v)),
     'minusculas, digitos, guion o guion bajo, sin empezar por "langfuse"'),
    ('afinado.pasadas', lambda v: _entero(v) and v >= 2, 'entero >= 2'),
    ('afinado.factor_margen', lambda v: _numero(v) and v > 0, 'numero > 0'),
    ('afinado.margen_guardias', lambda v: _numero(v) and v >= 0, 'numero >= 0'),
    ('afinado.max_candidatos', lambda v: _entero(v) and v >= 1, 'entero >= 1'),
    ('afinado.fallos_seguidos', lambda v: _entero(v) and v >= 1, 'entero >= 1'),
    ('afinado.tope_gasto', lambda v: _numero(v) and v > 0, 'numero > 0'),
    ('afinado.entorno', lambda v: isinstance(v, str) and bool(ENTORNO_DE_TRAZAS.match(v)),
     'minusculas, digitos, guion o guion bajo, sin empezar por "langfuse"'),
]

_AUSENTE = object()


def _leer(obj, ruta):
    actual = obj
    for clave in ruta.split('.'):
        if not isinstance(actual, dict) or clave not in actual:
            return _AUSENTE
        actual = actual[clave]
    return actual


def validar_config(bruto):
    fallos = []
    for clave, es_valido, esperado in REGLAS:
        valor = _leer(bruto, clave)
        if valor is _AUSENTE:
            fallos.append(f'falta la clave {clave}')
            continue
        if not es_valido(valor):
            fallos.append(f'{clave}: se esperaba {esperado} y hay {json.dumps(valor)}')

    # Los dos margenes de palabras de VD-08 solo tienen sentido en escalones.
    aviso = _leer(bruto, 'margenes.palabras_aviso')
    bloqueo = _leer(bruto, 'margenes.palabras_bloqueo')
    if _fraccion(aviso) and _fraccion(bloqueo) and bloqueo <= aviso:
        fallos.append('margenes.palabras_bloqueo debe ser mayor que margenes.palabras_aviso')

    # Si las llamadas de medicion cayeran en el entorno de las novelas, el
    # gasto de una vuelta se sumaria al de un libro y nadie lo notaria.
    entorno = _leer(bruto, 'trazas.entorno')
    afinado = _leer(bruto, 'afinado.entorno')
    if isinstance(entorno, str) and isinstance(afinado, str) and entorno == afinado:
        fallos.append('afinado.entorno debe ser distinto de trazas.entorno')

    minimo = _leer(bruto, 'margenes.capitulos_min')
    maximo = _leer(bruto, 'margenes.capitulos_max')
    if _numero(minimo) and _numero(maximo) and maximo < minimo:
        fallos.append('margenes.capitulos_max debe ser mayor o igual que margenes.capitulos_min')

    if fallos:
        detalle = '\n  - '.join(fallos)
        raise ErrorConfig(f'config.json no es valido:\n  - {detalle}')
    return bruto


def cargar_config(ruta='config.json'):
    try:
        with open(ruta, encoding='utf-8') as fichero:
            bruto = json.load(fichero)
    except (OSError, ValueError) as e:
        raise ErrorConfig(f'no se pudo leer {ruta}: {e}') from e
    return validar_config(bruto)
