# §22 Informe de trazas: lo que se lee de vuelta de Langfuse, agregado.
#
# Las trazas contestan por que el modelo contesto lo que contesto, pero una a
# una. La pregunta de la que sale este fichero es otra: en que se va el gasto de
# una novela entera, que roles cuestan, que capitulos se atascan y si lo caro es
# ademas lo bueno. Eso no se ve mirando trazas de una en una.
#
# **Los numeros los saca esto y el juicio lo pone un modelo**, que es la misma
# division que ya hace el gate de §8: la formula en codigo, la lectura fuera. Al
# analista no se le manda la traza cruda -son decenas de megas y casi todo es
# ruido-, se le manda este agregado mas las muestras que el propio agregado
# senala. Si el informe estuviera mal, el analisis heredaria el error sin
# poder verlo, y por eso esto no interpreta nada: cuenta.
import json
from collections import defaultdict

from .canon_cc import CanonCC, DIMENSIONES, auditar_gate, notas_en_lista
from .trazas import sesion_de, Trazas
from .trazas_cc import _config_de_trazas

# Cuantas observaciones se piden por vuelta. Una novela de seis capitulos deja
# del orden de cien, asi que con una pagina suele bastar; el bucle esta por las
# que no.
PAGINA = 100

# Las muestras que se le ensenan al analista. No es una preferencia estetica:
# mandarle las cuarenta llamadas costaria mas que el capitulo que analiza.
MUESTRAS = 5

# Los grupos de campos que hay que pedirle a la API para que conteste con el
# gasto. No es una lista de nombres de campo sino de grupos, y el que falte sale
# a null sin avisar de nada.
CAMPOS = 'core,model,usage,cost,metadata'


def _campo(obj, *nombres):
    """Un campo de una observacion, venga como venga."""
    for nombre in nombres:
        if isinstance(obj, dict):
            if obj.get(nombre) is not None:
                return obj[nombre]
        else:
            valor = getattr(obj, nombre, None)
            if valor is not None:
                return valor
    return None


def _numero(valor):
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0


def _paginar(api, sesion, **extra):
    """Todas las paginas de una consulta. El cursor de Langfuse se llama `cursor`."""
    salida = []
    cursor = None
    while True:
        pagina = api.observations.get_many(
            session_id=sesion, limit=PAGINA, cursor=cursor, **extra)
        datos = _campo(pagina, 'data') or []
        salida.extend(datos)
        cursor = _campo(_campo(pagina, 'meta') or {}, 'cursor', 'nextCursor')
        if not cursor or not datos:
            break
    return salida


def recoger(config, sesion, aviso=None):
    """Todas las observaciones de una novela, en dos pasadas que se cruzan por id.

    La API sirve dos caras distintas de la misma observacion y no las junta, y
    esto cuesta media tarde si no esta escrito: **sin `fields` viene el nombre y
    nada mas**, y pidiendo `fields` vienen el modelo, los tokens, el coste y la
    metadata pero el nombre llega siempre vacio. Como el `id` sale en las dos,
    se piden las dos y se cosen aqui por el.

    Que una columna salga a cero casi nunca significa que no se mando: significa
    que no se pidio. Antes de tocar como se escribe una traza, comprobar aqui.
    """
    trazas = Trazas(_config_de_trazas(config), aviso=aviso)
    if not trazas.activa or trazas.api is None:
        return None, trazas.motivo or 'no hay cliente de Langfuse'

    try:
        gasto = _paginar(trazas.api, sesion)
        marcas = _paginar(trazas.api, sesion, fields=CAMPOS)
    except Exception as e:
        return None, 'Langfuse no contesto: {}'.format(e)
    finally:
        trazas.cerrar()

    detalle = {}
    for obs in marcas:
        meta = _campo(obs, 'metadata')
        detalle[_campo(obs, 'id')] = {
            'metadata': meta if isinstance(meta, dict) else {},
            'modelo': _campo(obs, 'model'),
            'uso': _campo(obs, 'usage_details', 'usageDetails') or {},
            'coste': _numero(_campo(obs, 'total_cost', 'totalCost', 'calculatedTotalCost')),
        }

    observaciones = []
    for obs in gasto:
        clave = _campo(obs, 'id')
        extra = detalle.get(clave) or {}
        observaciones.append({
            'id': clave,
            'nombre': _campo(obs, 'name') or 'sin-nombre',
            'tipo': str(_campo(obs, 'type') or '').lower(),
            'modelo': extra.get('modelo'),
            'uso': extra.get('uso') or {},
            'coste': extra.get('coste') or 0,
            'latencia': _numero(_campo(obs, 'latency')),
            'traza': _campo(obs, 'trace_id', 'traceId'),
            'metadata': extra.get('metadata') or {},
        })
    return observaciones, None


def _meta(obs, clave):
    return (obs.get('metadata') or {}).get(clave)


def _vacio():
    return {'llamadas': 0, 'tokens': 0, 'entrada': 0, 'salida': 0, 'cache_leida': 0,
            'cache_escrita': 0, 'coste': 0.0, 'ms': 0}


def _sumar(cubo, obs):
    uso = obs.get('uso') or {}
    cubo['llamadas'] += 1
    cubo['entrada'] += _numero(uso.get('input'))
    cubo['salida'] += _numero(uso.get('output'))
    cubo['cache_leida'] += _numero(uso.get('cache_read_input_tokens'))
    cubo['cache_escrita'] += _numero(uso.get('cache_creation_input_tokens'))
    cubo['tokens'] += _numero(_meta(obs, 'tokens_totales')) or sum(
        _numero(v) for v in uso.values())
    cubo['coste'] += _numero(obs.get('coste'))
    # La duracion real la sabe quien hizo la llamada; la latencia de Langfuse
    # aqui mide lo que tardo el hook en escribir, que no es lo mismo.
    cubo['ms'] += _numero(_meta(obs, 'duracion_ms'))
    return cubo


def agregar(observaciones, canon=None, config=None):
    """El informe. Cuenta y no interpreta."""
    por_rol = defaultdict(_vacio)
    por_capitulo = defaultdict(_vacio)
    por_modelo = defaultdict(_vacio)
    directas = 0
    caras = []

    for obs in observaciones:
        # Solo lo observado en vivo tiene gasto: lo reconstruido del canon entra
        # en el arbol pero no cuenta tokens, y sumarlo seria inventarselos. Y de
        # lo observado, solo la `generation`: la `agent` que la envuelve lleva la
        # misma metadata, asi que contar las dos seria contar el capitulo dos
        # veces.
        if _meta(obs, 'origen') != 'hook' or obs['tipo'] != 'generation':
            continue
        directas += 1
        nombre = obs['nombre']
        capitulo = _meta(obs, 'capitulo')
        modelo = obs.get('modelo') or _meta(obs, 'modelo') or 'sin modelo'
        _sumar(por_rol[nombre], obs)
        _sumar(por_modelo[modelo], obs)
        _sumar(por_capitulo['cap-{:02d}'.format(capitulo) if capitulo else 'sin capitulo'], obs)
        caras.append({
            'rol': nombre, 'capitulo': capitulo, 'intento': _meta(obs, 'intento'),
            'dimension': _meta(obs, 'dimension'),
            'tokens': _numero(_meta(obs, 'tokens_totales')),
            'coste': _numero(obs.get('coste')),
            'ms': _numero(_meta(obs, 'duracion_ms')),
            'id': obs.get('id'), 'traza': obs.get('traza'),
        })

    total = _vacio()
    for cubo in por_rol.values():
        for clave in total:
            total[clave] += cubo[clave]

    informe = {
        'observaciones': len(observaciones),
        'llamadas': directas,
        'total': total,
        'por_rol': dict(por_rol),
        'por_capitulo': dict(por_capitulo),
        'por_modelo': dict(por_modelo),
        'mas_caras': sorted(caras, key=lambda c: (-c['coste'], -c['tokens']))[:MUESTRAS],
        'mas_lentas': sorted(caras, key=lambda c: -c['ms'])[:MUESTRAS],
    }
    if total['tokens']:
        # El reparto de cache es la palanca de coste mas grande que tiene este
        # sistema: el paquete de contexto de §7 se reenvia entero en cada
        # intento, y si no se esta leyendo de cache se esta pagando dos veces.
        informe['cache'] = {
            'leida': total['cache_leida'], 'escrita': total['cache_escrita'],
            'fresca': total['entrada'],
            'porcentaje_leido': round(
                100.0 * total['cache_leida'] / max(1, total['cache_leida'] + total['entrada']), 1),
        }
    if canon is not None and config is not None:
        informe['calidad'] = _calidad(canon, config, por_capitulo)
    return informe


def _calidad(canon, config, por_capitulo):
    """El cruce que de verdad interesa: lo que costo cada capitulo y lo que valio.

    Las notas no salen de Langfuse sino del canon, que es su fuente de verdad
    (§13). Aqui solo se ponen al lado del gasto.
    """
    filas = []
    for ficha in canon.escaleta():
        numero = ficha['numero']
        intentos = canon.intentos(numero)
        if not intentos:
            continue
        aprobado = canon.intento_aprobado(numero) or {}
        notas = notas_en_lista(aprobado.get('notas'))
        cuenta = auditar_gate(aprobado, config['gate']) if notas else {}
        gasto = por_capitulo.get('cap-{:02d}'.format(numero)) or _vacio()
        filas.append({
            'capitulo': numero,
            'intentos': len(intentos),
            'notas': dict(zip(DIMENSIONES, notas)) if notas else None,
            'media': cuenta.get('media'),
            'palabras': aprobado.get('palabras'),
            'tokens': gasto['tokens'],
            'coste': round(gasto['coste'], 4),
            'contexto_tokens': (canon.ficha_estado(numero)['contexto'] or {}).get('tokens'),
        })
    descartados = [
        {'capitulo': f['capitulo'], 'intento': i.get('intento'),
         'motivos': i.get('motivos') or [], 'vd08': i.get('vd08'),
         'notas': i.get('notas')}
        for f in filas
        for i in canon.intentos(f['capitulo'])
        if i.get('estado') == 'descartado'
    ]
    return {'capitulos': filas, 'descartados': descartados}


def texto(informe, sesion):
    """El informe en Markdown, que es lo que lee el analista."""
    t = informe['total']
    lineas = ['# Informe de trazas', '',
              'Sesion `{}` — {} observaciones, {} llamadas con gasto medido.'.format(
                  sesion, informe['observaciones'], informe['llamadas']), '']

    lineas += ['## Totales', '',
               '- Tokens: {:,} ({:,} frescos de entrada, {:,} de salida)'.format(
                   t['tokens'], t['entrada'], t['salida']),
               '- Cache: {:,} leidos, {:,} escritos'.format(
                   t['cache_leida'], t['cache_escrita']),
               '- Coste calculado: {:.4f}'.format(t['coste']),
               '- Tiempo de modelo: {:.1f} min'.format(t['ms'] / 60000.0), '']
    if informe.get('cache'):
        lineas += ['- De cada 100 tokens de entrada, {} salieron de cache'.format(
            informe['cache']['porcentaje_leido']), '']

    def tabla(titulo, datos, primera):
        filas = ['## {}'.format(titulo), '',
                 '| {} | llamadas | tokens | coste | min |'.format(primera),
                 '|---|---:|---:|---:|---:|']
        for clave, c in sorted(datos.items(), key=lambda kv: -kv[1]['tokens']):
            filas.append('| {} | {} | {:,} | {:.4f} | {:.1f} |'.format(
                clave, c['llamadas'], c['tokens'], c['coste'], c['ms'] / 60000.0))
        return filas + ['']

    # Un modelo que Langfuse no tiene en su lista sale a coste cero, y un cero
    # que en realidad es un "no lo se" envenena cualquier conclusion sobre
    # gasto. Se dice aqui en vez de dejar que el analista lo interprete.
    sin_precio = sorted(m for m, c in informe['por_modelo'].items()
                        if c['tokens'] and not c['coste'])
    if sin_precio:
        lineas += ['> Sin precio en Langfuse, cuentan tokens pero no coste: {}.'
                   ' El coste total de arriba se queda corto mientras no se les'
                   ' de precio en la lista de modelos de Langfuse.'.format(
                       ', '.join('`{}`'.format(m) for m in sin_precio)), '']

    lineas += tabla('Gasto por rol', informe['por_rol'], 'rol')
    lineas += tabla('Gasto por capitulo', informe['por_capitulo'], 'capitulo')
    lineas += tabla('Gasto por modelo', informe['por_modelo'], 'modelo')

    calidad = informe.get('calidad')
    if calidad:
        lineas += ['## Coste contra calidad', '',
                   '| cap | intentos | notas | media | palabras | contexto | tokens | coste |',
                   '|---:|---:|---|---:|---:|---:|---:|---:|']
        for f in calidad['capitulos']:
            notas = '/'.join(str(v) for v in (f['notas'] or {}).values()) or '—'
            lineas.append('| {} | {} | {} | {} | {} | {} | {:,} | {:.4f} |'.format(
                f['capitulo'], f['intentos'], notas, f['media'], f['palabras'],
                f['contexto_tokens'], f['tokens'], f['coste']))
        lineas += ['']
        if calidad['descartados']:
            lineas += ['### Intentos descartados', '']
            for d in calidad['descartados']:
                lineas.append('- cap {} intento {} (VD-08 {}): {}'.format(
                    d['capitulo'], d['intento'], d['vd08'],
                    '; '.join(d['motivos']) or 'sin motivos escritos'))
            lineas += ['']

    for titulo, clave, unidad in (('Llamadas mas caras', 'mas_caras', 'coste'),
                                  ('Llamadas mas lentas', 'mas_lentas', 'ms')):
        lineas += ['## {}'.format(titulo), '']
        for c in informe[clave]:
            lineas.append('- {} cap {} intento {}{} — {:,} tokens, {:.4f}, {:.0f}s'.format(
                c['rol'], c['capitulo'], c['intento'],
                ' ({})'.format(c['dimension']) if c['dimension'] else '',
                c['tokens'], c['coste'], c['ms'] / 1000.0))
        lineas += ['']

    return '\n'.join(lineas)


def construir(config, sesion=None, raiz=None, aviso=None):
    """El informe de una novela. Sin sesion, la de la novela que hay en disco."""
    canon = CanonCC(raiz or CanonCC().raiz)
    if not sesion:
        if not canon.existe:
            return None, 'no hay canon delegado y no me has dicho que sesion mirar'
        sesion = sesion_de(canon.brief())

    observaciones, motivo = recoger(config, sesion, aviso=aviso)
    if observaciones is None:
        return None, motivo
    if not observaciones:
        return None, 'Langfuse no tiene ninguna observacion de la sesion {}'.format(sesion)

    informe = agregar(observaciones, canon=canon if canon.existe else None,
                      config=config if canon.existe else None)
    informe['sesion'] = sesion
    return informe, None
