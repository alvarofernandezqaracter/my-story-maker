# §20 + §21 Trazas del camino delegado.
#
# El hook de §22 instrumenta en vivo porque ve cada llamada al pasar por la capa
# de agentes de §5. El camino delegado no pasa por ahi -orquesta una sesion de
# Claude Code- y §21 daba eso por perdido: "no hay donde instrumentar sin
# inventarse un punto unico que aqui no existe".
#
# Ese punto unico si existe, solo que no es una llamada: es el canon. El
# orquestador escribe en `estado.json` las tres notas, el minimo, la media, el
# recuento de graves y los motivos de **todos** los intentos, y en los demas
# ficheros lo que produjo cada rol. Con eso se reconstruye el arbol de §20
# despues de los hechos y se manda a Langfuse.
#
# **Es observabilidad reconstruida, y se dice en cada traza.** No hay latencia,
# ni tokens, ni coste, ni el prompt exacto: eso solo lo tiene quien hizo la
# llamada. Lo que si hay es el arbol, las notas, los veredictos y la auditoria
# del gate, que es de lo que salen los datos de DA-06. Cada traza va etiquetada
# `reconstruido` para que no se confunda con una que si trae gasto.
#
# Como el resto del paquete, esto no sabe que Langfuse existe: habla con la capa
# de §20 (`trazas.py`), que es la unica que lo sabe.
import os
import re
from pathlib import Path

from .canon_cc import CanonCC, DIMENSIONES, auditar_gate, notas_en_lista
from .entorno import cargar_entorno
from .trazas import CLAVES, id_de_traza, sesion_de, Trazas

# Un retoque del editor global es un encabezado `### RET-xx` de retoques.md
# (§11). Contarlos por el fichero y no por el canon es deliberado: el canon
# delegado no guarda los retoques, y el fichero es la salida de verdad.
RETOQUE = re.compile(r'^###\s+RET-', re.MULTILINE)

ETIQUETAS = ('delegado', 'reconstruido')


def traza_de(sesion, tramo):
    """El id de la traza de un tramo de esta novela (§21).

    Lo comparte con el hook de `trazas_hook.py`, y esa es toda la gracia: lo que
    se observo en vivo y lo que se reconstruye despues del canon acaban en la
    misma traza del capitulo en vez de en dos paralelas que nadie sabe
    juntar. Cada fuente se distingue por su etiqueta.
    """
    return id_de_traza('{}|{}'.format(sesion or 'sin-sesion', tramo))


def _config_de_trazas(config):
    """El perfil que ve la capa de §20, que es solo el bloque de trazas.

    Sigue existiendo como funcion, y no como acceso directo al bloque, porque es
    el unico sitio por el que pasan los tres que trazan -la reconstruccion, el
    hook y el informe- y conviene que sigan compartiendolo.
    """
    return {'trazas': (config or {}).get('trazas') or {}}


def texto_viaja(config):
    """Si el capitulo y su paquete de contexto salen dentro de la traza (§12).

    Son lo unico que un evaluador de Langfuse puede leer -no abre ficheros-, asi
    que sin esto no hay evaluacion de calidad posible. Se deja gobernado por
    `trazas.texto` porque mandar la novela entera a un servicio de fuera es una
    decision, no un detalle: quien no la quiera tomar apaga la clave y pierde el
    juez, no las trazas.
    """
    return bool(((config or {}).get('trazas') or {}).get('texto'))


def _meta(**extra):
    base = {'camino': 'delegado', 'origen': 'novela-cc', 'reconstruido': True}
    base.update({k: v for k, v in extra.items() if v is not None})
    return base


# El rol viaja en la metadata aunque ya sea el nombre de la observacion, y no es
# redundancia: las reglas de evaluacion de §20 filtran por `metadata`, `type`,
# `environment` y unas pocas columnas mas, y el nombre de la observacion no esta
# entre ellas. Sin esta clave no hay forma de soltarle un juez al escritor y solo
# al escritor.
ROLES = ('investigador', 'arquitecto', 'escritor', 'validador', 'cronista',
         'editor_global')


def disponibilidad(config):
    """Si la capa de §20 podria mandar algo, sin construir el cliente.

    La pagina pregunta esto cada vez que se abre el panel, y arrancar un cliente
    de Langfuse para contestar "no hay credencial" seria pagar por la respuesta.
    Comprueba lo mismo que `Trazas._arrancar` y en el mismo orden, para que el
    motivo que se lee aqui sea el motivo que daria la capa de verdad.
    """
    bloque = (config or {}).get('trazas') or {}
    if not bloque.get('activas'):
        return {'lista': False, 'motivo': 'trazas.activas esta a false en el perfil'}
    cargar_entorno()
    faltan = [c for c in CLAVES if not os.environ.get(c)]
    if faltan:
        return {'lista': False,
                'motivo': 'faltan en el entorno: {}'.format(', '.join(faltan))}
    try:
        import langfuse  # noqa: F401
    except ImportError as e:
        return {'lista': False,
                'motivo': 'falta el SDK: pip install "my-story-maker[trazas]" ({})'.format(e)}
    return {'lista': True, 'motivo': None}


def plan(canon, config):
    """Que se mandaria, sin mandar nada.

    La interfaz lo ensena antes de que nadie pulse nada: exportar deja marca en
    un servicio de fuera, y conviene ver primero el tamano de lo que sale.
    """
    escaleta = canon.escaleta()
    con_intentos = [c for c in escaleta if canon.intentos(c['numero'])]
    intentos = sum(len(canon.intentos(c['numero'])) for c in escaleta)
    puntuados = sum(
        1 for c in escaleta for i in canon.intentos(c['numero'])
        if notas_en_lista(i.get('notas')))
    texto_retoques, _ = canon.retoques()
    estado = canon.estado()

    # Lo que sale deja de ser un arbol de numeros en cuanto `trazas.texto` esta
    # puesta: sale la novela. Se cuenta antes para que se vea, que es justo lo
    # que esta funcion existe para hacer.
    con_texto = texto_viaja(config)
    palabras_fuera = 0
    if con_texto:
        for capitulo in escaleta:
            paquete, _ = canon.contexto(capitulo['numero'])
            palabras_fuera += len((paquete or '').split())
            for i in canon.intentos(capitulo['numero']):
                texto, _ = canon.texto_de_intento(i)
                palabras_fuera += len((texto or '').split())

    return {
        'sesion': sesion_de(canon.brief()),
        'entorno': ((config or {}).get('trazas') or {}).get('entorno'),
        'preparar': bool(canon.datos() or canon.escaleta()),
        'capitulos': len(con_intentos),
        'cerrar': estado == 'editado' and bool(texto_retoques),
        'intentos': intentos,
        # Tres notas, la media y el veredicto por intento puntuado, mas los
        # intentos que costo cada capitulo.
        'notas': puntuados * 5 + len(con_intentos),
        'retoques': len(RETOQUE.findall(texto_retoques or '')),
        'texto': con_texto,
        'palabras_fuera': palabras_fuera,
        'reconstruido': True,
    }


# ------------------------------------------------------------------ tramos

def _preparar(trazas, canon, sesion):
    datos = canon.datos()
    personajes = canon.personajes()
    escaleta = canon.escaleta()
    if not (datos or personajes or escaleta):
        return 0

    verificados = sum(1 for d in datos if d.get('estado') == 'verificado')
    with trazas.traza('preparar-novela', entrada=canon.brief(), sesion=sesion,
                      etiquetas=ETIQUETAS, metadata=_meta(),
                      trace_id=traza_de(sesion, 'preparar')) as traza:
        with trazas.paso('investigador', tipo='agent', entrada=canon.brief(),
                         metadata=_meta(rol='investigador', datos=len(datos))) as paso:
            paso.actualizar(output={'datos': len(datos), 'verificados': verificados,
                                    'categorias': sorted(
                                        {d.get('categoria') for d in datos if d.get('categoria')})})
        with trazas.paso('arquitecto', tipo='agent',
                         metadata=_meta(rol='arquitecto', capitulos=len(escaleta),
                                        personajes=len(personajes))) as paso:
            paso.actualizar(output={'capitulos': len(escaleta),
                                    'personajes': [p.get('id') for p in personajes]})
        traza.actualizar(output={'datos': len(datos), 'capitulos': len(escaleta),
                                 'personajes': len(personajes)})
    return 1


def _capitulo(trazas, canon, config, ficha, sesion, modelo=None):
    numero = ficha['numero']
    intentos = canon.intentos(numero)
    if not intentos:
        return 0
    con_texto = texto_viaja(config)
    estado_ficha = canon.ficha_estado(numero)
    contexto = estado_ficha['contexto'] or {}
    resumen = canon.resumen(numero)

    with trazas.traza(
        'escribir-capitulo',
        entrada={'numero': numero, 'titulo': ficha.get('titulo'),
                 'objetivo': ficha.get('objetivo')},
        sesion=sesion, etiquetas=ETIQUETAS,
        metadata=_meta(capitulo=numero, acto=ficha.get('acto')),
        trace_id=traza_de(sesion, 'cap-{:02d}'.format(numero)),
    ) as traza:
        # El paquete de §7 es un retriever: lee el canon y no cambia nada.
        paquete, _ruta_paquete = canon.contexto(numero) if con_texto else (None, None)
        with trazas.paso('reunir-contexto', tipo='retriever',
                         entrada={'capitulo': numero},
                         metadata=_meta(capitulo=numero)) as paso:
            salida = {
                'ruta': canon.ruta_contexto(numero).as_posix(),
                'tokens': contexto.get('tokens'),
                'recortes': contexto.get('recortes') or [],
            }
            if paquete:
                salida['paquete'] = paquete
            paso.actualizar(output=salida)

        for intento in intentos:
            _intento(trazas, config, numero, intento, modelo,
                     canon=canon if con_texto else None, paquete=paquete)

        if resumen:
            with trazas.paso('cronista', tipo='agent',
                             entrada={'capitulo': numero,
                                      'intento': estado_ficha['intento_aprobado']},
                             metadata=_meta(rol='cronista', capitulo=numero), modelo=modelo) as paso:
                paso.actualizar(output={
                    'hilos_abiertos': len(resumen.get('hilos_abiertos') or []),
                    'hilos_cerrados': len(resumen.get('hilos_cerrados') or []),
                    'eventos': len(resumen.get('eventos') or []),
                    'cambios_personaje': len(resumen.get('cambios_personaje') or []),
                })

        aprobado = canon.intento_aprobado(numero)
        traza.actualizar(output={'estado': estado_ficha['estado'],
                                 'intento_aprobado': estado_ficha['intento_aprobado'],
                                 'palabras': (aprobado or {}).get('palabras')})
        # Cuantos intentos costo el capitulo va en la traza, no en el gate: es la
        # medida del capitulo entero y §20 la pone aqui a proposito.
        traza.nota('intentos', len(intentos),
                   'intentos hasta {}'.format(estado_ficha['estado']))
    return 1


def _intento(trazas, config, numero, intento, modelo=None, canon=None, paquete=None):
    k = intento.get('intento')
    notas = notas_en_lista(intento.get('notas'))
    comun = _meta(capitulo=numero, intento=k,
                  tipo_reintento=intento.get('tipo_reintento'))

    # El paquete que recibio y el capitulo que devolvio, en la misma observacion
    # y no repartidos entre madre e hija: un evaluador de Langfuse solo lee el
    # input, el output y la metadata de la observacion a la que apunta, y no
    # puede mirar ni a sus hermanas ni a sus hijas. Si esto se separa, el juez
    # se queda sin con que comparar.
    entrada = {'capitulo': numero, 'intento': k}
    if paquete:
        entrada['paquete'] = paquete
    salida = {'ruta': intento.get('ruta'),
              'palabras': intento.get('palabras'),
              'parrafos': intento.get('parrafos')}
    if canon is not None:
        texto, _ = canon.texto_de_intento(intento)
        if texto:
            salida['texto'] = texto

    with trazas.paso('escritor', tipo='agent', entrada=entrada,
                     metadata={**comun, 'rol': 'escritor'}, modelo=modelo) as paso:
        paso.actualizar(output=salida)

    # VD-08 es uno de los dos puntos donde se decide sin preguntar a nadie (§20).
    with trazas.paso('vd-08-extension', tipo='evaluator',
                     entrada={'palabras': intento.get('palabras'),
                              'parrafos': intento.get('parrafos')},
                     metadata=comun) as paso:
        veredicto = intento.get('vd08') or 'sin_dato'
        paso.actualizar(output={'veredicto': veredicto})
        paso.nota('vd-08', veredicto == 'ok', 'escalon: {}'.format(veredicto))

    if not notas:
        # Descartado antes de llamar a los validadores: no hubo gate que trazar.
        return

    # Tres validadores que no se ven: en este camino no es una opcion de
    # configuracion sino la forma del camino (§21), y por eso van uno por paso.
    for dimension, nota in zip(DIMENSIONES, notas):
        with trazas.paso('validador', tipo='agent',
                         entrada={'capitulo': numero, 'intento': k,
                                  'dimension': dimension},
                         metadata=_meta(rol='validador', capitulo=numero, intento=k,
                                        dimension=dimension),
                         modelo=modelo) as paso:
            paso.actualizar(output={'dimension': dimension, 'nota': nota})
            paso.nota(dimension, nota)

    cuenta = auditar_gate(intento, config['gate'])
    with trazas.paso('gate', tipo='evaluator',
                     entrada={'notas': dict(zip(DIMENSIONES, notas)),
                              'umbrales': config['gate']},
                     metadata=comun) as paso:
        paso.actualizar(output={'minima': cuenta['minima'], 'media': cuenta['media'],
                                'graves': cuenta['graves'],
                                'aprueba': cuenta['aprueba'],
                                'motivos': cuenta['motivos']})
        for dimension, nota in zip(DIMENSIONES, notas):
            paso.nota(dimension, nota)
        paso.nota('media', cuenta['media'])
        paso.nota('aprueba', cuenta['aprueba'],
                  '; '.join(cuenta['motivos']) or 'sin motivos en contra')
        # La auditoria de §21: la formula la aplica esto, pero la suma que se
        # guardo la hizo un modelo. Si no coinciden hay que poder buscarlo.
        if not cuenta['cuadra']:
            paso.nota('gate-cuadra', False,
                      'el canon guardo aprueba={} y la formula da {}'.format(
                          cuenta['aprueba_canon'], cuenta['aprueba']))


def _cerrar(trazas, canon, sesion, modelo=None):
    texto, ruta = canon.retoques()
    if not texto:
        return 0
    total = len(RETOQUE.findall(texto))
    with trazas.traza('cerrar-novela', sesion=sesion, etiquetas=ETIQUETAS,
                      metadata=_meta(), trace_id=traza_de(sesion, 'cerrar')) as traza:
        with trazas.paso('editor_global', tipo='agent',
                         entrada={'capitulos': len(canon.resumenes())},
                         metadata=_meta(rol='editor_global', retoques=total), modelo=modelo) as paso:
            paso.actualizar(output={'retoques': total, 'ruta': ruta})
        traza.actualizar(output={'retoques': total, 'ruta': ruta})
    return 1


# ------------------------------------------------------------------ entrada

def exportar(config, raiz=None, modelo=None, aviso=None):
    """Manda a Langfuse el canon delegado entero, reconstruido.

    Devuelve lo que se mando y por que no, si no se mando. Como en §20, ningun
    fallo de observabilidad es un error del sistema: si la capa no esta activa,
    esto lo cuenta y devuelve.
    """
    canon = CanonCC(raiz or CanonCC().raiz)
    if not canon.existe:
        return {'enviado': False,
                'motivo': 'no hay canon delegado en {}'.format(
                    Path(canon.raiz).as_posix())}

    resumen = plan(canon, config)
    trazas = Trazas(_config_de_trazas(config), aviso=aviso)
    if not trazas.activa:
        return {'enviado': False, 'motivo': trazas.motivo, 'plan': resumen}

    sesion = resumen['sesion']
    try:
        tramos = _preparar(trazas, canon, sesion)
        for ficha in canon.escaleta():
            tramos += _capitulo(trazas, canon, config, ficha, sesion, modelo)
        tramos += _cerrar(trazas, canon, sesion, modelo)
    finally:
        trazas.cerrar()

    if not trazas.activa:
        return {'enviado': False, 'motivo': trazas.motivo, 'plan': resumen}
    return {'enviado': True, 'trazas': tramos, 'sesion': sesion, 'plan': resumen,
            'motivo': None}
