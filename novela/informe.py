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
from pathlib import Path

from .canon_cc import CanonCC, DIMENSIONES, auditar_gate, notas_en_lista
from .trazas import sesion_de, Trazas
from .trazas_cc import _config_de_trazas
from .trazas_hook import DIARIO

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


def del_diario(raiz, sesion=None):
    """Las mismas llamadas, leidas del diario local del hook (§22).

    El diario se escribe pase lo que pase con Langfuse, asi que es lo que queda
    cuando el servicio no contesta. Cada linea se traduce a la forma que espera
    `agregar`, para que el informe salga por el mismo sitio y no haya dos
    maneras de contar lo mismo.

    **El diario no sabe de dinero.** Lleva el modelo y el reparto de tokens,
    pero el coste lo calcula Langfuse cruzandolos con su lista de precios, y
    aqui no hay lista. El coste sale a cero y quien lo lea tiene que saberlo:
    por eso el informe se marca con su procedencia y el texto pone una raya
    donde iria el dinero, en vez de un cero que se lee como gratis.
    """
    ruta = Path(raiz) / DIARIO
    if not ruta.exists():
        return None, 'tampoco hay diario local en {}'.format(ruta)

    observaciones = []
    rotas = 0
    repetidas = 0
    vistas = set()
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        if not linea.strip():
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            rotas += 1
            continue
        if sesion and d.get('sesion') and d['sesion'] != sesion:
            continue
        # El diario solo sabe anadir: el hook escribe una linea por evento y
        # nadie la borra, asi que un evento entregado dos veces -o una sesion
        # reanudada sobre el mismo canon- deja la misma llamada repetida. En
        # Langfuse eso no se nota porque la observacion lleva id y se solapa;
        # aqui hay que descartarlo o cada numero sale al doble. La firma es lo
        # que no pueden compartir dos llamadas distintas: mismo rol, misma
        # dimension, mismo capitulo e intento, y ademas los mismos milisegundos
        # exactos y los mismos tokens.
        firma = (d.get('rol'), d.get('dimension'), d.get('capitulo'),
                 d.get('intento'), d.get('duracion_ms'), d.get('tokens'))
        if firma in vistas:
            repetidas += 1
            continue
        vistas.add(firma)
        observaciones.append({
            'id': d.get('traza'),
            'nombre': d.get('rol') or 'sin-nombre',
            # El diario solo anota llamadas a subagentes, que es justo lo que
            # `agregar` cuenta: se presentan como la `generation` del hook para
            # que el filtro de alli valga igual sin tener que tocarlo.
            'tipo': 'generation',
            'modelo': d.get('modelo'),
            'uso': d.get('reparto') or {},
            'coste': 0,
            'latencia': 0,
            'traza': d.get('traza'),
            'metadata': {
                'origen': 'hook',
                'capitulo': d.get('capitulo'),
                'intento': d.get('intento'),
                'dimension': d.get('dimension'),
                'tokens_totales': d.get('tokens'),
                'duracion_ms': d.get('duracion_ms'),
                'modelo': d.get('modelo'),
            },
        })
    if not observaciones:
        return None, 'el diario local de {} no tiene ninguna llamada de esa sesion'.format(ruta)
    reparos = []
    if repetidas:
        reparos.append('{} linea(s) repetidas descartadas'.format(repetidas))
    if rotas:
        reparos.append('{} linea(s) ilegibles'.format(rotas))
    return observaciones, ('; '.join(reparos) if reparos else None)


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
    # Lo que no se sabe no se rellena con un cero: un cero se lee como gratis.
    del_diario_ = informe.get('procedencia') == 'diario'
    dinero = (lambda v: '—') if del_diario_ else (lambda v: '{:.4f}'.format(v))

    lineas = ['# Informe de trazas', '',
              'Sesion `{}` — {} observaciones, {} llamadas con gasto medido.'.format(
                  sesion, informe['observaciones'], informe['llamadas']), '']
    if del_diario_:
        lineas += ['> **Sin Langfuse: esto sale del diario local del hook.**'
                   ' {}. El diario anota quien, cuando, cuanto tardo y cuantos'
                   ' tokens costo, asi que lo de abajo es tan real como siempre'
                   ' salvo el dinero: el coste lo calcula Langfuse cruzando'
                   ' modelo y tokens con su lista de precios, y sin el no hay'
                   ' precio que aplicar. Donde iria dinero va una raya. No lo'
                   ' rellenes al leerlo.'.format(
                       informe.get('sin_langfuse', 'Langfuse no contesto')), '']

    lineas += ['## Totales', '',
               '- Tokens: {:,} ({:,} frescos de entrada, {:,} de salida)'.format(
                   t['tokens'], t['entrada'], t['salida']),
               '- Cache: {:,} leidos, {:,} escritos'.format(
                   t['cache_leida'], t['cache_escrita']),
               '- Coste calculado: {}'.format(dinero(t['coste'])),
               '- Tiempo de modelo: {:.1f} min'.format(t['ms'] / 60000.0), '']
    if informe.get('cache'):
        lineas += ['- De cada 100 tokens de entrada, {} salieron de cache'.format(
            informe['cache']['porcentaje_leido']), '']

    def tabla(titulo, datos, primera):
        filas = ['## {}'.format(titulo), '',
                 '| {} | llamadas | tokens | coste | min |'.format(primera),
                 '|---|---:|---:|---:|---:|']
        for clave, c in sorted(datos.items(), key=lambda kv: -kv[1]['tokens']):
            filas.append('| {} | {} | {:,} | {} | {:.1f} |'.format(
                clave, c['llamadas'], c['tokens'], dinero(c['coste']), c['ms'] / 60000.0))
        return filas + ['']

    # Un modelo que Langfuse no tiene en su lista sale a coste cero, y un cero
    # que en realidad es un "no lo se" envenena cualquier conclusion sobre
    # gasto. Se dice aqui en vez de dejar que el analista lo interprete.
    sin_precio = [] if del_diario_ else sorted(
        m for m, c in informe['por_modelo'].items() if c['tokens'] and not c['coste'])
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
            lineas.append('| {} | {} | {} | {} | {} | {} | {:,} | {} |'.format(
                f['capitulo'], f['intentos'], notas, f['media'], f['palabras'],
                f['contexto_tokens'], f['tokens'], dinero(f['coste'])))
        lineas += ['']
        if calidad['descartados']:
            lineas += ['### Intentos descartados', '']
            for d in calidad['descartados']:
                lineas.append('- cap {} intento {} (VD-08 {}): {}'.format(
                    d['capitulo'], d['intento'], d['vd08'],
                    '; '.join(d['motivos']) or 'sin motivos escritos'))
            lineas += ['']

    # Sin coste la primera lista sigue valiendo, porque el desempate ya era por
    # tokens; lo que cambia es el titulo, que si no prometeria dinero.
    caras = 'Llamadas con mas tokens' if del_diario_ else 'Llamadas mas caras'
    for titulo, clave in ((caras, 'mas_caras'), ('Llamadas mas lentas', 'mas_lentas')):
        lineas += ['## {}'.format(titulo), '']
        for c in informe[clave]:
            lineas.append('- {} cap {} intento {}{} — {:,} tokens, {}, {:.0f}s'.format(
                c['rol'], c['capitulo'], c['intento'],
                ' ({})'.format(c['dimension']) if c['dimension'] else '',
                c['tokens'], dinero(c['coste']), c['ms'] / 1000.0))
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
    if not observaciones:
        # Langfuse no esta, o no contesta, o no tiene nada de esta sesion. El
        # diario del hook si esta: es local y se escribe pase lo que pase. Se
        # cae a el en vez de no dar informe, porque casi todo lo que el analisis
        # necesita -llamadas, roles, capitulos, intentos, tokens y duracion- lo
        # sabe el diario. Lo unico que no es el dinero, y eso se declara.
        motivo = motivo or 'Langfuse no tiene ninguna observacion de la sesion {}'.format(sesion)
        observaciones, aviso_diario = del_diario(canon.raiz, sesion)
        if observaciones is None:
            return None, '{}; {}'.format(motivo, aviso_diario)
        if aviso and aviso_diario:
            aviso(aviso_diario)
        procedencia, porque = 'diario', motivo
    else:
        procedencia, porque = 'langfuse', None

    informe = agregar(observaciones, canon=canon if canon.existe else None,
                      config=config if canon.existe else None)
    informe['sesion'] = sesion
    informe['procedencia'] = procedencia
    if porque:
        informe['sin_langfuse'] = porque
    return informe, None
