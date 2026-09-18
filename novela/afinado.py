# AFINADO.md. El loop que mide el prompt de un rol y decide si un candidato
# merece sustituirlo.
#
# Lo determinista vive aqui y solo aqui: preparar los casos, leer las
# respuestas, contar, medir el ruido y dar el veredicto. Lo que NO vive aqui es
# escribir el prompt candidato, que lo hace un modelo con el taller delante, ni
# llamar al subagente, que lo hace la sesion de Claude Code para que la medida
# salga del arnes donde el prompt corre de verdad (AFINADO.md §6).
#
# Dos reglas de este fichero, las dos de AFINADO.md §5:
#
# 1. **Los casos no se guardan en el repositorio.** Se escriben en una carpeta
#    temporal de fuera y se borran al cerrar la vuelta. El validador es un
#    subagente con `Read` sobre el proyecto y un examinado que lee el examen
#    escribe para el examen.
# 2. **La clave no se escribe donde estan los casos.** Va en un fichero hermano
#    de la carpeta de la vuelta, nunca dentro de ella.
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .trazas import Trazas

# Nombre de la carpeta de trabajo dentro del temporal del sistema. No es una
# clave de config: no es un numero ni un umbral, es donde el sistema operativo
# dice que van las cosas que se tiran.
CARPETA = 'novela-afinado'

MARCADOR = 'vuelta.json'

# La dimension del primer loop. Cuando entre un segundo rol esto dejara de ser
# una constante, pero inventarle hoy una clave de config seria un numero que no
# gobierna nada.
DIMENSION = 'anacronismos'

# Las otras dos dimensiones, que son la guardia de efecto lateral: las tres
# comparten `agentes/validador.md`, asi que un prompt que mejora los
# anacronismos puede estropearlas.
HERMANAS = ('continuidad', 'logica_ritmo')

PARTICIONES = ('taller', 'reserva')


class ErrorAfinado(Exception):
    """La vuelta no puede seguir. Se para antes de gastar llamadas."""


# ---- donde vive una vuelta


def carpeta_trabajo():
    return Path(tempfile.gettempdir()) / CARPETA


def ruta_vuelta(numero):
    return carpeta_trabajo() / 'vuelta-{:02d}'.format(int(numero))


def ruta_clave(numero):
    """La clave, fuera de la carpeta de la vuelta y a proposito (§5)."""
    return carpeta_trabajo() / 'clave-{:02d}.json'.format(int(numero))


def vuelta_en_curso():
    """La vuelta abierta, o None.

    Lo llama el hook de trazas: mientras hay una vuelta abierta, sus llamadas
    no son de ninguna novela y no pueden colgarse de su sesion (§6).
    """
    raiz = carpeta_trabajo()
    if not raiz.is_dir():
        return None
    abiertas = []
    for carpeta in sorted(raiz.glob('vuelta-*')):
        try:
            marca = json.loads((carpeta / MARCADOR).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if marca.get('abierta'):
            abiertas.append(marca)
    return abiertas[-1] if abiertas else None


def abrir_vuelta(numero, entorno, casos):
    """Escribe los casos en disco y marca la vuelta como abierta.

    Cada caso deja dos ficheros con el nombre que el subagente espera leer, y
    ni el nombre de la carpeta ni el de los ficheros dicen si el caso esta
    sembrado: eso vive en la clave, que se escribe fuera.
    """
    if not casos:
        raise ErrorAfinado('no hay casos: una vuelta sin casos no mide nada')

    destino = ruta_vuelta(numero)
    if destino.exists():
        shutil.rmtree(destino)
    (destino / 'casos').mkdir(parents=True)
    (destino / 'respuestas').mkdir()

    clave = {}
    for caso in casos:
        cid = caso['id']
        carpeta = destino / 'casos' / cid
        carpeta.mkdir()
        (carpeta / 'capitulo.md').write_text(caso['capitulo'], encoding='utf-8')
        (carpeta / 'contexto.md').write_text(caso['contexto'], encoding='utf-8')
        clave[cid] = {'tipo': caso['tipo'], 'particion': caso['particion'],
                      'marca': caso.get('marca'), 'nivel': caso.get('nivel'),
                      'origen': caso.get('origen')}

    marca = {'vuelta': int(numero), 'entorno': entorno, 'abierta': True,
             'sesion': 'afinado-{:02d}'.format(int(numero)),
             'casos': len(casos)}
    (destino / MARCADOR).write_text(
        json.dumps(marca, ensure_ascii=False, indent=2), encoding='utf-8')
    ruta_clave(numero).write_text(
        json.dumps(clave, ensure_ascii=False, indent=2), encoding='utf-8')
    return marca


def cerrar_vuelta(numero, borrar_casos=True):
    """Cierra la vuelta. Los casos se van; la clave y las respuestas se quedan
    hasta que alguien las tire, porque son lo que se puede releer."""
    destino = ruta_vuelta(numero)
    marcador = destino / MARCADOR
    if marcador.exists():
        marca = json.loads(marcador.read_text(encoding='utf-8'))
        marca['abierta'] = False
        marcador.write_text(
            json.dumps(marca, ensure_ascii=False, indent=2), encoding='utf-8')
    if borrar_casos and (destino / 'casos').is_dir():
        shutil.rmtree(destino / 'casos')


# ---- leer lo que devolvio el subagente


def leer_bloque(bruto):
    """El bloque de revision de una respuesta, o None si no pasa la forma.

    Es VD-10 de SPEC.md §9 aplicado al bloque unico: un solo bloque, de la
    dimension que se pidio, con nota entera de 1 a 5. Lo que no cumpla esto no
    es una nota baja, es una respuesta que no sirve, y cuenta como tal.
    """
    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto)
        except ValueError:
            return None
    if not isinstance(bruto, dict):
        return None
    revisiones = bruto.get('revisiones')
    if not isinstance(revisiones, list) or len(revisiones) != 1:
        return None
    bloque = revisiones[0]
    if not isinstance(bloque, dict):
        return None
    nota = bloque.get('nota')
    if not isinstance(nota, int) or isinstance(nota, bool) or not 1 <= nota <= 5:
        return None
    if bloque.get('dimension') not in (DIMENSION,) + HERMANAS:
        return None
    return bloque


def _bloquearia_el_gate(bloque, suelo):
    """Si con este bloque el gate de SPEC.md §8 pararia el capitulo.

    Son dos caminos y hay que mirar los dos, porque el gate mira los dos: la
    nota por debajo del suelo, **o** una sola incidencia grave, que veta por si
    sola pase lo que pase con las notas. Mirar solo la nota daria por no
    detectado un anacronismo que el validador vio y marco como grave, que es
    justo lo contrario de lo que esta metrica quiere contar.
    """
    if bloque['nota'] < suelo:
        return True
    for incidencia in bloque.get('incidencias') or []:
        if isinstance(incidencia, dict) and incidencia.get('severidad') == 'grave':
            return True
    return False


def _respuestas(numero, prompt):
    """Las respuestas de un prompt, agrupadas por pasada.

    El nombre del fichero es `<caso>-p<pasada>.json`, que es lo unico que la
    sesion tiene que respetar al volcar lo que devolvio el subagente.
    """
    carpeta = ruta_vuelta(numero) / 'respuestas' / prompt
    por_pasada = {}
    for fichero in sorted(carpeta.glob('*-p*.json')):
        tallo = fichero.stem
        cid, _, pasada = tallo.rpartition('-p')
        try:
            pasada = int(pasada)
        except ValueError:
            continue
        try:
            bruto = json.loads(fichero.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            bruto = None
        por_pasada.setdefault(pasada, {})[cid] = bruto
    return por_pasada


# ---- las cuentas


def _fraccion(parte, total):
    return round(parte / total, 4) if total else None


def medir_pasada(config, clave, respuestas, particion=None):
    """Las metricas de una pasada: la objetivo y las guardias contables.

    Todo sale de comparar la nota con `gate.nota_minima`, que es el mismo suelo
    con el que el gate de SPEC.md §8 bloquea un capitulo. No hay ningun umbral
    propio de este fichero, y no debe haberlo.
    """
    suelo = config['gate']['nota_minima']
    sembrados = aciertos = limpios = falsos = validas = total = 0
    niveles = {}

    for cid, bruto in respuestas.items():
        ficha = clave.get(cid)
        if not ficha:
            continue
        if particion and ficha['particion'] != particion:
            continue
        total += 1
        bloque = leer_bloque(bruto)
        if bloque is None:
            # Una respuesta sin forma no vota en la metrica objetivo: contarla
            # como fallo de deteccion premiaria a un prompt que deja de
            # contestar. Cuenta en `forma`, que es su guardia.
            continue
        validas += 1
        bloquea = _bloquearia_el_gate(bloque, suelo)
        if ficha['tipo'] == 'sembrado':
            sembrados += 1
            acierta = 1 if bloquea else 0
            aciertos += acierta
            # El nivel no decide nada: no entra en ninguna metrica ni en el
            # veredicto. Se cuenta para poder leer despues **que clase** de
            # anacronismo se le escapa al prompt, que es lo que dice por donde
            # tiene que ir el candidato siguiente.
            if ficha.get('nivel') is not None:
                cuenta = niveles.setdefault(
                    str(ficha['nivel']), {'sembrados': 0, 'aciertos': 0})
                cuenta['sembrados'] += 1
                cuenta['aciertos'] += acierta
        else:
            limpios += 1
            falsos += 1 if bloquea else 0

    return {'casos': total, 'validas': validas,
            'sembrados': sembrados, 'aciertos': aciertos,
            'limpios': limpios, 'falsos': falsos,
            'deteccion': _fraccion(aciertos, sembrados),
            'falsos_positivos': _fraccion(falsos, limpios),
            'forma': _fraccion(validas, total),
            'niveles': niveles}


def _media(valores):
    limpios = [v for v in valores if v is not None]
    return round(sum(limpios) / len(limpios), 4) if limpios else None


def _resolucion(cuantos):
    """El salto mas pequeno que una fraccion puede dar con `cuantos` casos.

    Con doce capitulos limpios, un solo falso positivo mueve la guardia 0,0833
    y no hay manera de moverla menos: por debajo de eso la guardia no distingue
    nada, solo reparte.
    """
    return round(1.0 / cuantos, 4) if cuantos else None


def _tolerancia(ruido, resolucion, margen):
    """Cuanto puede empeorar una guardia sin que cuente como empeorar.

    Manda la mayor de dos cosas. El **ruido** es cuanto se movio esa guardia
    entre dos pasadas identicas del vigente. La **resolucion** es el salto mas
    pequeno que la guardia sabe dar con los casos que hay.

    Sin la segunda, una guardia que el vigente clava en su valor perfecto se
    rompe con el primer caso que falle, y entonces no protege: impide, que es
    la regla de AFINADO.md §2. Paso de verdad en la vuelta 1: el vigente hizo
    cero falsos positivos de doce y el candidato uno, y con eso se cayo una
    promocion que la metrica objetivo pedia.
    """
    medidas = [v for v in (ruido, resolucion) if v is not None]
    return round(max(medidas) * margen, 4) if medidas else 0.0


def _ruido(valores):
    """La diferencia entre la mejor y la peor pasada del MISMO prompt.

    Se usa el recorrido y no la desviacion tipica a proposito: con tres pasadas
    la desviacion tipica es un numero que aparenta precision que no tiene, y lo
    que hay que contestar es «cuanto se movio esto sin que cambiara nada».
    """
    limpios = [v for v in valores if v is not None]
    return round(max(limpios) - min(limpios), 4) if len(limpios) > 1 else None


def medir(config, numero, prompt, particion=None):
    """Las `afinado.pasadas` de un prompt, con su media y su ruido."""
    try:
        clave = json.loads(ruta_clave(numero).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise ErrorAfinado(
            'sin la clave de la vuelta {} no hay nada que puntuar: {}'.format(
                numero, e)) from None
    por_pasada = _respuestas(numero, prompt)
    if not por_pasada:
        raise ErrorAfinado(
            'no hay respuestas de "{}" en la vuelta {}'.format(prompt, numero))

    pasadas = [medir_pasada(config, clave, respuestas, particion)
               for _, respuestas in sorted(por_pasada.items())]
    detecciones = [p['deteccion'] for p in pasadas]
    # La resolucion se toma de la pasada mas pobre, no de la mejor: si una
    # pasada contesto menos casos, la guardia distingue menos en esa vuelta, y
    # el que decide tiene que saberlo por el lado prudente.
    limpios = [p['limpios'] for p in pasadas if p['limpios']]
    contados = [p['casos'] for p in pasadas if p['casos']]
    return {
        'prompt': prompt,
        'particion': particion or 'todas',
        'pasadas': pasadas,
        'deteccion': _media(detecciones),
        'ruido': _ruido(detecciones),
        'falsos_positivos': _media([p['falsos_positivos'] for p in pasadas]),
        'forma': _media([p['forma'] for p in pasadas]),
        'ruido_falsos': _ruido([p['falsos_positivos'] for p in pasadas]),
        'ruido_forma': _ruido([p['forma'] for p in pasadas]),
        'resolucion_falsos': _resolucion(min(limpios) if limpios else 0),
        'resolucion_forma': _resolucion(min(contados) if contados else 0),
    }


def comparar(config, vigente, candidato, hermanas=None, coste=None):
    """El veredicto. La regla entera, impresa, como el gate de SPEC.md §8.

    `aprueba = mejora > ruido * factor_margen  y  ninguna guardia empeora`

    El ruido que manda es el del VIGENTE, no el del candidato: es la medida de
    cuanto se mueve esta metrica sin que nada cambie, y es contra eso contra lo
    que hay que demostrar algo.
    """
    factor = config['afinado']['factor_margen']
    margen = config['afinado']['margen_guardias']
    ruido = vigente.get('ruido')
    mejora = None
    if vigente.get('deteccion') is not None and candidato.get('deteccion') is not None:
        mejora = round(candidato['deteccion'] - vigente['deteccion'], 4)

    umbral = round(ruido * factor, 4) if ruido is not None else None

    guardias = []
    guardias.append(_guardia(
        'falsos_positivos', vigente.get('falsos_positivos'),
        candidato.get('falsos_positivos'), 'no sube',
        _tolerancia(vigente.get('ruido_falsos'),
                    vigente.get('resolucion_falsos'), margen)))
    guardias.append(_guardia(
        'forma', vigente.get('forma'), candidato.get('forma'), 'no baja',
        _tolerancia(vigente.get('ruido_forma'),
                    vigente.get('resolucion_forma'), margen)))
    if hermanas:
        guardias.append(_guardia(
            'notas_hermanas', hermanas.get('vigente'), hermanas.get('candidato'),
            'no baja',
            _tolerancia(hermanas.get('ruido'), hermanas.get('resolucion'), margen)))
    if coste:
        guardias.append(_guardia(
            'coste_llamada', coste.get('vigente'), coste.get('candidato'),
            'no sube', _tolerancia(coste.get('ruido'), None, margen)))

    rotas = [g['metrica'] for g in guardias if g['empeora']]
    bate = (mejora is not None and umbral is not None and mejora > umbral)

    return {
        'mejora': mejora, 'ruido': ruido, 'factor_margen': factor, 'umbral': umbral,
        'margen_guardias': margen,
        'bate_el_ruido': bate, 'guardias': guardias, 'rotas': rotas,
        'promueve': bool(bate and not rotas),
        'operacion': 'mejora {} {} umbral {} (ruido {} x factor {}){}'.format(
            mejora, '>' if bate else '<=', umbral, ruido, factor,
            '' if not rotas else '; guardias rotas: ' + ', '.join(
                '{} ({} -> {}, tolerancia {})'.format(
                    g['metrica'], g['antes'], g['ahora'], g['tolerancia'])
                for g in guardias if g['empeora'])),
    }


def _guardia(metrica, antes, ahora, sentido, tolerancia=0.0):
    """Una guardia, con el margen que se le consiente.

    `tolerancia` no es indulgencia: es lo que esa guardia no sabe distinguir,
    medido en el paso 3. Empeorar menos que eso no es empeorar, es la misma
    medida otra vez.
    """
    if antes is None or ahora is None:
        # Sin medida no hay guardia, y una guardia que no se pudo medir no se
        # da por cumplida: se dice que falta.
        return {'metrica': metrica, 'antes': antes, 'ahora': ahora,
                'sentido': sentido, 'tolerancia': tolerancia,
                'empeora': True, 'motivo': 'sin medir'}
    diferencia = round(ahora - antes, 6)
    empeora = (diferencia > tolerancia if sentido == 'no sube'
               else -diferencia > tolerancia)
    return {'metrica': metrica, 'antes': antes, 'ahora': ahora,
            'sentido': sentido, 'tolerancia': tolerancia,
            'empeora': bool(empeora), 'motivo': None}


def parar(config, fallos_seguidos, candidatos_probados, gasto):
    """Los cuatro frenos de STOP (AFINADO.md §4), en un solo sitio."""
    bloque = config['afinado']
    if candidatos_probados >= bloque['max_candidatos']:
        return 'se agotaron los {} candidatos de la vuelta'.format(
            bloque['max_candidatos'])
    if fallos_seguidos >= bloque['fallos_seguidos']:
        return '{} candidatos seguidos sin batir el ruido'.format(fallos_seguidos)
    if gasto is not None and gasto >= bloque['tope_gasto']:
        return 'el gasto de la vuelta llego a {} $'.format(bloque['tope_gasto'])
    return None


# ---- los casos, que viven fuera


def conjunto(particion):
    return 'afinado-{}-{}'.format(DIMENSION, particion)


def _capa(config, aviso=None):
    """La capa de trazas con el entorno de afinado en vez del de las novelas."""
    bloque = dict((config or {}).get('trazas') or {})
    bloque['entorno'] = config['afinado']['entorno']
    return Trazas({'trazas': bloque}, aviso=aviso)


def subir_casos(config, casos, aviso=None):
    """Sube los casos a Langfuse y **no los deja en el repositorio** (§5)."""
    capa = _capa(config, aviso)
    if not capa.activa:
        raise ErrorAfinado(
            'sin Langfuse no hay donde guardar los casos: {}'.format(capa.motivo))
    subidos = {p: 0 for p in PARTICIONES}
    fallidos = []
    try:
        for particion in PARTICIONES:
            capa.crear_conjunto(
                conjunto(particion),
                descripcion='Casos de afinado del validador de {} ({})'.format(
                    DIMENSION, particion),
                metadata={'rol': 'validador', 'dimension': DIMENSION,
                          'particion': particion})
        for caso in casos:
            particion = caso['particion']
            if particion not in PARTICIONES:
                raise ErrorAfinado('particion desconocida: {}'.format(particion))
            if not capa.subir_caso(
                    conjunto(particion), caso['id'],
                    entrada={'capitulo': caso['capitulo'],
                             'contexto': caso['contexto']},
                    clave={'tipo': caso['tipo'], 'marca': caso.get('marca'),
                           'nivel': caso.get('nivel')},
                    metadata={'origen': caso.get('origen'),
                              'particion': particion}):
                # Se cuenta lo que subio, no lo que se intento. La capa se apaga
                # sola al primer fallo (§20), asi que contar intentos daria un
                # conjunto completo sobre un conjunto vacio, y la vuelta
                # siguiente mediria contra casos que no estan.
                fallidos.append(caso['id'])
                continue
            subidos[particion] += 1
    finally:
        capa.cerrar()
    if fallidos:
        raise ErrorAfinado(
            'no subieron {} casos de {} (el primero, {}): {}'.format(
                len(fallidos), len(casos), fallidos[0], capa.motivo))
    return subidos


def bajar_casos(config, aviso=None):
    capa = _capa(config, aviso)
    if not capa.activa:
        raise ErrorAfinado(
            'sin Langfuse no hay casos que bajar: {}'.format(capa.motivo))
    casos = []
    try:
        for particion in PARTICIONES:
            for item in capa.leer_casos(conjunto(particion)):
                entrada = item['entrada'] or {}
                clave = item['clave'] or {}
                casos.append({
                    'id': item['id'], 'particion': particion,
                    'tipo': clave.get('tipo'), 'marca': clave.get('marca'),
                    'nivel': clave.get('nivel'),
                    'origen': (item['metadata'] or {}).get('origen'),
                    'capitulo': entrada.get('capitulo') or '',
                    'contexto': entrada.get('contexto') or ''})
    finally:
        capa.cerrar()
    return sorted(casos, key=lambda c: c['id'])


# ---- promover, que es un commit y nada mas


def promover(numero, rol, origen, raiz='.'):
    """Escribe el prompt candidato en su sitio y lo commitea solo (§8).

    El commit no lleva nada mas dentro a proposito: asi deshacerlo es un
    `git revert` y no hay que separar nada.
    """
    destino = Path(raiz) / 'agentes' / '{}.md'.format(rol)
    if not destino.exists():
        raise ErrorAfinado('no existe el prompt {}'.format(destino))
    texto_nuevo = Path(origen).read_text(encoding='utf-8')
    if texto_nuevo == destino.read_text(encoding='utf-8'):
        raise ErrorAfinado('el candidato es identico al vigente')
    destino.write_text(texto_nuevo, encoding='utf-8')

    asunto = mensaje_de_promocion(numero, rol)
    subprocess.run(['git', 'add', str(destino)], cwd=raiz, check=True)
    subprocess.run(['git', 'commit', '-m', asunto], cwd=raiz, check=True)
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=raiz, check=True,
                         capture_output=True, text=True).stdout.strip()
    return {'commit': sha, 'asunto': asunto, 'deshacer': 'git revert ' + sha[:12]}


def mensaje_de_promocion(numero, rol):
    """La forma fija del asunto. Es codigo y no prosa para que no derive: lo
    que hace reversible una promocion es poder encontrarla."""
    return 'feat(afinado): vuelta {:02d} promueve el prompt de {}'.format(
        int(numero), rol)


# ---- lo que se imprime


def texto(numero, medidas, veredicto=None):
    lineas = ['# Afinado — vuelta {:02d}'.format(int(numero)), '']
    for medida in medidas:
        lineas.append('## {} sobre la particion {}'.format(
            medida['prompt'], medida['particion']))
        lineas.append('')
        lineas.append('| Pasada | Sembrados | Aciertos | Deteccion | Limpios |'
                      ' Falsos | Forma |')
        lineas.append('|---:|---:|---:|---:|---:|---:|---:|')
        for i, p in enumerate(medida['pasadas'], 1):
            lineas.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
                i, p['sembrados'], p['aciertos'], p['deteccion'],
                p['limpios'], p['falsos'], p['forma']))
        lineas.append('')
        lineas.append('- **Deteccion media**: {}'.format(medida['deteccion']))
        lineas.append('- **Ruido** (mejor pasada menos peor, mismo prompt): {}'
                      .format(medida['ruido']))
        lineas.append('- Falsos positivos: {} | forma: {}'.format(
            medida['falsos_positivos'], medida['forma']))
        lineas.append('')
    if veredicto:
        lineas.append('## Veredicto')
        lineas.append('')
        lineas.append('```')
        lineas.append(veredicto['operacion'])
        lineas.append('```')
        lineas.append('')
        lineas.append('**{}**'.format(
            'PROMUEVE' if veredicto['promueve'] else 'NO PROMUEVE'))
    return '\n'.join(lineas)
