# §12 Configuracion. Un unico config.json en la raiz. El harness lo carga al
# arrancar, lo valida entero y para si falta una clave o un valor cae fuera de
# rango: una errata en un umbral sale mas barata descubierta al arrancar.
import json
import math
import re

# Lo que Langfuse acepta como nombre de entorno (§20). Se valida aqui, al
# arrancar, por la misma razon que todo lo demas de este fichero: un entorno mal
# escrito se descubre tres capitulos despues, cuando las trazas no aparecen
# donde se las busca.
ENTORNO_DE_TRAZAS = re.compile(r'^(?!langfuse)[a-z0-9_\-]{1,40}$')

ROLES = [
    'investigador', 'arquitecto', 'escritor', 'validador', 'cronista', 'editor_global',
]


class ErrorConfig(Exception):
    """config.json no sirve. El harness para antes de hacer nada."""


def _entero(v):
    # Los booleanos de JSON son int en Python y aqui no cuelan como enteros.
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _fraccion(v):
    return _numero(v) and 0 < v < 1


def _modelos_por_rol(v):
    return isinstance(v, dict) and all(
        isinstance(v.get(rol), str) and v.get(rol) for rol in ROLES
    )


# (clave, predicado, que se espera)
REGLAS = [
    ('ejecucion.modo', lambda v: v in ('simulado', 'real', 'claude_code'),
     '"simulado", "real" o "claude_code"'),
    ('gate.nota_minima', lambda v: _entero(v) and 1 <= v <= 5, 'entero entre 1 y 5'),
    ('gate.media_minima', lambda v: _numero(v) and 1 <= v <= 5, 'numero entre 1 y 5'),
    ('gate.max_intentos', lambda v: _entero(v) and v >= 1, 'entero >= 1'),
    ('contexto.tope_contexto', lambda v: _entero(v) and v > 0, 'entero > 0'),
    ('contexto.ventana_resumenes', lambda v: _entero(v) and v >= 0, 'entero >= 0'),
    ('contexto.palabras_enganche', lambda v: _entero(v) and v >= 0, 'entero >= 0'),
    ('validador.modo', lambda v: v in ('unico', 'separado'), '"unico" o "separado"'),
    ('interfaz.puerto', lambda v: _entero(v) and 1024 <= v <= 65535,
     'entero entre 1024 y 65535'),
    # Por cual de los dos caminos mira la interfaz al abrirse (§19, §21). No
    # cierra el otro: la pagina puede cambiar de canon sin reiniciar nada.
    ('interfaz.camino', lambda v: v in ('delegado', 'harness'),
     '"delegado" o "harness"'),
    ('margenes.capitulos_min', lambda v: _numero(v) and 0 < v <= 1, 'numero en (0, 1]'),
    ('margenes.capitulos_max', lambda v: _numero(v) and v >= 1, 'numero >= 1'),
    ('margenes.palabras_aviso', _fraccion, 'fraccion en (0, 1)'),
    ('margenes.palabras_bloqueo', _fraccion, 'fraccion en (0, 1)'),
    ('margenes.parrafos_min', lambda v: _entero(v) and v >= 1, 'entero >= 1'),
    ('trazas.activas', lambda v: isinstance(v, bool), 'booleano'),
    ('trazas.entorno', lambda v: isinstance(v, str) and bool(ENTORNO_DE_TRAZAS.match(v)),
     'minusculas, digitos, guion o guion bajo, sin empezar por "langfuse"'),
    ('modelo_por_rol', _modelos_por_rol, 'un modelo por cada rol de §5'),
    ('busqueda_web', lambda v: isinstance(v, bool), 'booleano'),
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
