# §8 Gate de calidad. Codigo puro: tres notas y sus incidencias entran, una
# decision sale. El gate no sabe si las revisiones vinieron de una llamada al
# validador o de tres (§5), solo que ya pasaron VD-10.
from .esquemas import DIMENSIONES
from .util import redondear


def notas(revisiones):
    return [r['nota'] for r in revisiones]


def media(valores):
    if not valores:
        return 0
    return sum(valores) / len(valores)


def incidencias_graves(revisiones):
    graves = []
    for r in revisiones:
        for i in r.get('incidencias') or []:
            if i.get('severidad') == 'grave':
                graves.append({**i, 'dimension': r['dimension']})
    return graves


def gate(revisiones, config_gate):
    """aprueba = min(notas) >= nota_minima y media(notas) >= media_minima
    y ninguna incidencia grave.

    La incidencia grave veta por si sola: un capitulo puede sacar tres cuatros y
    caer por una contradiccion de canon, porque eso no se arregla puntuando mas
    alto.
    """
    ns = notas(revisiones)
    minima = min(ns) if ns else 0
    promedio = media(ns)
    graves = incidencias_graves(revisiones)

    motivos = []
    if minima < config_gate['nota_minima']:
        motivos.append('nota minima {} por debajo de {}'.format(
            minima, config_gate['nota_minima']))
    if promedio < config_gate['media_minima']:
        motivos.append('media {:.2f} por debajo de {}'.format(
            redondear(promedio, 2), config_gate['media_minima']))
    if graves:
        motivos.append('{} incidencia(s) grave(s)'.format(len(graves)))

    return {
        'aprueba': not motivos,
        'minima': minima,
        'media': promedio,
        'graves': graves,
        'motivos': motivos,
    }


def mejor_intento(intentos):
    """Al agotar intentos se conserva el de mejor media, en estado propuesto (§8)."""
    con_revisiones = [
        i for i in intentos
        if isinstance(i.get('revisiones'), list) and i['revisiones']
    ]
    if not con_revisiones:
        return intentos[-1] if intentos else None

    mejor = con_revisiones[0]
    for actual in con_revisiones[1:]:
        if media(notas(actual['revisiones'])) > media(notas(mejor['revisiones'])):
            mejor = actual
    return mejor


def incidencias_ordenadas(revisiones):
    """Las incidencias del intento anterior, ordenadas por severidad (§8)."""
    orden = {'grave': 0, 'aviso': 1}
    todas = []
    for r in revisiones:
        for i in r.get('incidencias') or []:
            todas.append({**i, 'dimension': r['dimension']})

    def clave(incidencia):
        dimension = incidencia.get('dimension')
        return (
            orden.get(incidencia.get('severidad'), 9),
            DIMENSIONES.index(dimension) if dimension in DIMENSIONES else len(DIMENSIONES),
        )

    return sorted(todas, key=clave)
