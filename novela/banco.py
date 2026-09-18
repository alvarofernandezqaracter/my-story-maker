# §5-§9 de AUTOAPRENDIZAJE.md. El banco: mide un prompt, propone otro, compara
# y promueve si gana.
#
# **Esto no escribe novelas.** Arranca el mismo camino delegado de §21 de
# SPEC.md -una sesion de Claude Code con el prompt del rol dentro- una vez por
# caso, y cuenta lo que sale. Lo unico que cambia entre dos corridas es el texto
# del prompt; si cambiara algo mas, la comparacion no diria nada.
#
# **Y por que esto si es codigo**, cuando la novela es una conversacion: aqui no
# hay juicio dentro. Contar tokens, comparar dos numeros contra un margen y
# parar a la quinta vuelta es aritmetica. Lo generativo -proponer la variante,
# juzgar la calidad- sigue fuera: en el optimizador y en los jueces de Langfuse.
import json
import re
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import casos as casos_mod
from .metricas import agregar, medir, tokens_estimados

OBJETIVOS = 'autoaprendizaje/objetivos'
RONDAS = 'autoaprendizaje/rondas'
OPTIMIZADOR = 'autoaprendizaje/optimizador.md'

# El nombre del agente al vuelo. Da igual cual sea -vive lo que dura una
# llamada- pero tiene que ser el mismo en las dos banderas.
AGENTE = 'banco'

FRONTMATTER = re.compile(r'\A---\r?\n.*?\r?\n---\r?\n', re.DOTALL)

CABECERA = ('Tus instrucciones completas van pegadas aqui abajo, enteras.'
            ' No busques ningun fichero: en esta sesion no hay repositorio que leer.')


class ErrorBanco(Exception):
    """El banco no puede correr. Se para antes de gastar nada."""


# --- el objetivo --------------------------------------------------------------

def cargar_objetivo(ident, raiz=OBJETIVOS):
    ruta = Path(raiz) / '{}.json'.format(ident)
    if not ruta.is_file():
        disponibles = ', '.join(sorted(o['id'] for o in listar_objetivos(raiz))) or 'ninguno'
        raise ErrorBanco('no hay ningun objetivo que se llame {}. Hay: {}'.format(
            ident, disponibles))
    try:
        objetivo = json.loads(ruta.read_text(encoding='utf-8'))
    except ValueError as e:
        raise ErrorBanco('{} no es JSON valido: {}'.format(ruta, e)) from e

    for clave in ('id', 'rol', 'prompt', 'piezas', 'objetivo'):
        if clave not in objetivo:
            raise ErrorBanco('al objetivo {} le falta la clave {}'.format(ident, clave))
    if objetivo['prompt'] not in objetivo['piezas']:
        raise ErrorBanco('el prompt {} tiene que ser una de las piezas'.format(
            objetivo['prompt']))
    return objetivo


def listar_objetivos(raiz=OBJETIVOS):
    salida = []
    for ruta in sorted(Path(raiz).glob('*.json')) if Path(raiz).is_dir() else []:
        try:
            salida.append(json.loads(ruta.read_text(encoding='utf-8')))
        except ValueError:
            continue
    return salida


# --- el prompt que se mide ----------------------------------------------------

def sin_frontmatter(texto):
    return FRONTMATTER.sub('', texto or '', count=1).strip()


def componer(objetivo, candidato=None, raiz='.'):
    """El prompt efectivo de un rol, montado de una vez.

    En produccion el subagente lee sus ficheros al arrancar (§18 de SPEC.md);
    aqui se pegan de antemano, porque el banco corre fuera del repositorio y no
    hay nada que leer. El contenido es el mismo y el orden tambien: lo que
    cambia es cuando se junta.
    """
    partes = [CABECERA]
    for pieza in objetivo['piezas']:
        if pieza == objetivo['prompt'] and candidato is not None:
            partes.append(sin_frontmatter(candidato))
            continue
        ruta = Path(raiz) / pieza
        if not ruta.is_file():
            raise ErrorBanco('falta la pieza {} del objetivo {}'.format(pieza, objetivo['id']))
        partes.append(sin_frontmatter(ruta.read_text(encoding='utf-8')))
    return '\n\n'.join(p for p in partes if p)


def prompt_vigente(objetivo, raiz='.'):
    return (Path(raiz) / objetivo['prompt']).read_text(encoding='utf-8')


# --- el gasto -----------------------------------------------------------------

class Gasto:
    """Lo que lleva gastado la sesion del banco, con su tope.

    El tope no es un lujo: una ronda son decenas de llamadas y un objetivo mal
    puesto puede encadenar cinco rondas sin mejorar nada. Se mira antes de cada
    corrida, no despues, porque despues ya se gasto.
    """

    def __init__(self, tope):
        self.tope = tope
        self.total = 0.0
        self._cerrojo = threading.Lock()

    @property
    def agotado(self):
        return self.total >= self.tope

    def suma(self, cuanto):
        with self._cerrojo:
            self.total += float(cuanto or 0)
            return self.total


# --- una corrida --------------------------------------------------------------

def _ejecutable(config):
    comando = (config.get('lanzador') or {}).get('comando') or 'claude'
    ruta = shutil.which(comando)
    if not ruta:
        raise ErrorBanco('no encuentro el CLI de Claude Code ({}). El banco lo'
                         ' necesita: mide arrancando el mismo camino que escribe'
                         ' las novelas.'.format(comando))
    return ruta


def _uso(salida):
    """Tokens de salida y coste de una sesion, de su JSON."""
    modelos = salida.get('modelUsage') or {}
    tokens = sum(int(m.get('outputTokens') or 0) for m in modelos.values()
                 if isinstance(m, dict))
    return tokens, salida.get('total_cost_usd'), sorted(modelos)


def _texto_del_fichero(trabajo):
    """Lo que escribio el rol, cuando su salida es un fichero y no la respuesta.

    El escritor de §5 escribe su borrador en disco y devuelve la ruta; medir su
    respuesta seria medir la ruta. Se coge el ultimo .md que aparecio.
    """
    ficheros = sorted(Path(trabajo).glob('**/*.md'), key=lambda f: f.stat().st_mtime)
    if not ficheros:
        return ''
    return ficheros[-1].read_text(encoding='utf-8', errors='replace')


def correr_caso(prompt, caso, objetivo, config, gasto, ejecutable=None):
    """Una llamada: el prompt bajo prueba, con un caso delante.

    Corre **fuera del repositorio**, en un directorio temporal. Dos motivos y
    los dos importan: que no se cuele el CLAUDE.md del proyecto en lo que se
    esta midiendo, y que el candidato no pueda leer el repositorio -ni las
    rubricas, ni los casos, ni las rondas anteriores-.
    """
    if gasto.agotado:
        return {'caso': caso['id'], 'ok': False, 'motivo': 'tope de gasto',
                'salida': '', 'tokens_prompt': tokens_estimados(prompt)}

    ajustes = (config.get('autoaprendizaje') or {})
    agente = {'description': 'rol {} bajo prueba'.format(objetivo['rol']),
              'prompt': prompt}
    if objetivo.get('herramientas'):
        agente['tools'] = objetivo['herramientas']
    if objetivo.get('modelo'):
        agente['model'] = objetivo['modelo']

    orden = [ejecutable or _ejecutable(config), '-p',
             '--agents', json.dumps({AGENTE: agente}, ensure_ascii=False),
             '--agent', AGENTE,
             '--output-format', 'json',
             '--permission-mode', (config.get('lanzador') or {}).get('permisos', 'acceptEdits')]

    trabajo = tempfile.mkdtemp(prefix='banco-')
    try:
        proceso = subprocess.run(
            orden, input=caso.get('entrada') or '', cwd=trabajo, text=True,
            capture_output=True, encoding='utf-8', errors='replace',
            timeout=ajustes.get('tope_segundos', 600))
        try:
            bruto = json.loads(proceso.stdout)
        except ValueError:
            return {'caso': caso['id'], 'ok': False,
                    'motivo': 'la sesion no devolvio JSON: {}'.format(
                        (proceso.stderr or proceso.stdout or '')[:200]),
                    'salida': '', 'tokens_prompt': tokens_estimados(prompt)}

        tokens_salida, coste, modelos = _uso(bruto)
        gasto.suma(coste)
        texto = (_texto_del_fichero(trabajo) if objetivo.get('salida') == 'fichero'
                 else bruto.get('result') or '')
        return {
            'caso': caso['id'], 'ok': not bruto.get('is_error') and bool(texto),
            'motivo': None if texto else 'sin salida',
            'salida': texto,
            'tokens_prompt': tokens_estimados(prompt),
            'tokens_salida': tokens_salida,
            'coste_usd': coste,
            'segundos': (bruto.get('duration_ms') or 0) / 1000.0,
            'modelos': modelos,
            'sesion_cc': bruto.get('session_id'),
        }
    except subprocess.TimeoutExpired:
        return {'caso': caso['id'], 'ok': False, 'motivo': 'se paso del tiempo',
                'salida': '', 'tokens_prompt': tokens_estimados(prompt)}
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


def correr(prompt, lista, objetivo, config, gasto, aviso=None):
    """El prompt contra todos los casos de una particion."""
    ajustes = (config.get('autoaprendizaje') or {})
    ejecutable = _ejecutable(config)
    anchura = max(1, int(ajustes.get('corridas_en_paralelo', 1)))
    # Cada caso se corre mas de una vez cuando hace falta: dos llamadas con el
    # mismo prompt y el mismo caso no dan el mismo numero, y con pocos casos esa
    # varianza se come el margen. Repetir es la unica forma barata de saber si
    # una diferencia es del prompt o del dia.
    repeticiones = max(1, int(ajustes.get('repeticiones', 1)))
    tareas = [caso for _ in range(repeticiones) for caso in lista]
    with ThreadPoolExecutor(max_workers=anchura) as piscina:
        corridas = list(piscina.map(
            lambda caso: correr_caso(prompt, caso, objetivo, config, gasto, ejecutable),
            tareas))
    fallidas = [c for c in corridas if not c['ok']]
    if fallidas and aviso:
        aviso('{} de {} corridas sin salida: {}'.format(
            len(fallidas), len(corridas),
            ', '.join('{} ({})'.format(c['caso'], c['motivo']) for c in fallidas[:3])))
    return corridas


# --- los numeros --------------------------------------------------------------

def _nombres_medidos(objetivo):
    nombres = [objetivo['objetivo']['metrica']]
    nombres += [g['metrica'] for g in objetivo.get('guardias') or []]
    nombres += list(objetivo.get('informativas') or [])
    return list(dict.fromkeys(nombres))


def resumir(corridas, lista, objetivo, config):
    """De todas las corridas a un numero por metrica."""
    por_id = {c['id']: c for c in lista}
    nombres = _nombres_medidos(objetivo)
    detalle = []
    for corrida in corridas:
        caso = por_id.get(corrida['caso']) or {}
        detalle.append({'caso': corrida['caso'], 'ok': corrida['ok'],
                        'motivo': corrida.get('motivo'),
                        'medidas': medir(corrida, caso, config, nombres)})

    agregados = {}
    como = {objetivo['objetivo']['metrica']: objetivo['objetivo'].get('agregado', 'media')}
    for guardia in objetivo.get('guardias') or []:
        como[guardia['metrica']] = guardia.get('agregado', 'media')
    for nombre in nombres:
        valores = [d['medidas'].get(nombre) for d in detalle if d['ok']]
        agregados[nombre] = agregar(valores, como.get(nombre, 'media'))

    # `validas` cuenta casos distintos y no corridas: con repeticiones, contar
    # corridas haria que tres casos repetidos cuatro veces pasaran por doce, y
    # el suelo de `casos_minimos` dejaria de significar lo que dice.
    return {'agregados': agregados, 'detalle': detalle,
            'corridas': len(corridas),
            'casos': len({d['caso'] for d in detalle}),
            'validas': len({d['caso'] for d in detalle if d['ok']}),
            'coste_usd': sum(c.get('coste_usd') or 0 for c in corridas)}


def mejora(vigente, candidato, direccion):
    """Cuanto mejora el candidato al vigente, en tanto por uno."""
    if not isinstance(vigente, (int, float)) or not isinstance(candidato, (int, float)):
        return None
    if vigente == 0:
        return None
    if direccion == 'sube':
        return (candidato - vigente) / abs(float(vigente))
    return (vigente - candidato) / abs(float(vigente))


def merece_la_reserva(ganancia, margen):
    """Si vale la pena gastar la reserva midiendo a este candidato.

    La reserva son seis llamadas mas -el vigente y el candidato- y solo sirven
    para decidir. Un candidato que ni en el taller llega al margen no va a
    promover, asi que medirlo alli es pagar por una respuesta que ya se tiene.
    """
    return isinstance(ganancia, (int, float)) and ganancia >= margen


def comparar(resumen_vigente, resumen_candidato, objetivo, config):
    """La regla de promocion de §7, entera y con sus motivos escritos."""
    ajustes = (config.get('autoaprendizaje') or {})
    margen = ajustes.get('margen_mejora', 0.1)
    minimos = ajustes.get('casos_minimos', 4)

    metrica = objetivo['objetivo']['metrica']
    direccion = objetivo['objetivo'].get('direccion', 'baja')
    vig = resumen_vigente['agregados'].get(metrica)
    cand = resumen_candidato['agregados'].get(metrica)
    ganancia = mejora(vig, cand, direccion)

    motivos = []
    if resumen_candidato['validas'] < minimos:
        motivos.append('solo {} casos validos y hacen falta {}'.format(
            resumen_candidato['validas'], minimos))
    if ganancia is None:
        motivos.append('no se puede comparar {}: vigente {} y candidato {}'.format(
            metrica, vig, cand))
    elif ganancia < margen:
        motivos.append('{} mejora {:.1%} y el margen es {:.1%}'.format(
            metrica, ganancia, margen))

    guardias = []
    for guardia in objetivo.get('guardias') or []:
        nombre = guardia['metrica']
        valor = resumen_candidato['agregados'].get(nombre)
        antes = resumen_vigente['agregados'].get(nombre)
        pasa, por_que = True, None
        if valor is None:
            pasa, por_que = False, 'sin numero'
        elif 'maximo' in guardia and valor > guardia['maximo']:
            pasa, por_que = False, 'supera el maximo {}'.format(guardia['maximo'])
        elif 'minimo' in guardia and valor < guardia['minimo']:
            pasa, por_que = False, 'baja del minimo {}'.format(guardia['minimo'])
        elif guardia.get('no_peor_que_vigente') and isinstance(antes, (int, float)):
            # Una guardia con minimo mira hacia arriba; una con maximo, hacia
            # abajo. El empate vale: lo que no vale es empeorar.
            if 'minimo' in guardia and valor < antes:
                pasa, por_que = False, 'peor que el vigente ({} < {})'.format(valor, antes)
            if 'maximo' in guardia and valor > antes:
                pasa, por_que = False, 'peor que el vigente ({} > {})'.format(valor, antes)
        guardias.append({'metrica': nombre, 'valor': valor, 'vigente': antes,
                         'pasa': pasa, 'motivo': por_que})
        if not pasa:
            motivos.append('guardia {}: {}'.format(nombre, por_que))

    return {'gana': not motivos, 'ganancia': ganancia, 'metrica': metrica,
            'vigente': vig, 'candidato': cand, 'guardias': guardias,
            'motivos': motivos}


# --- el optimizador -----------------------------------------------------------

def _peores(resumen, objetivo, cuantos=4):
    """Los casos en los que el prompt vigente lo hace peor.

    Es lo unico del taller que ve el optimizador, y es justo lo que necesita:
    donde falla, no donde acierta.
    """
    metrica = objetivo['objetivo']['metrica']
    al_reves = objetivo['objetivo'].get('direccion', 'baja') == 'baja'
    con_numero = [d for d in resumen['detalle']
                  if isinstance(d['medidas'].get(metrica), (int, float))]
    return sorted(con_numero, key=lambda d: d['medidas'][metrica],
                  reverse=al_reves)[:cuantos]


def _encargo_optimizador(objetivo, vigente, resumen, cuantos):
    lineas = [
        'OBJETIVO: {}'.format(objetivo['id']),
        'ROL: {}'.format(objetivo['rol']),
        'METRICA QUE HAY QUE MEJORAR: {} ({})'.format(
            objetivo['objetivo']['metrica'],
            'cuanto mas baja, mejor' if objetivo['objetivo'].get('direccion', 'baja') == 'baja'
            else 'cuanto mas alta, mejor'),
        # Sin esto el optimizador adivina que cuenta la metrica, y adivina mal:
        # en la primera ronda real escribio tres prompts mas largos y con mas
        # estructura para bajar unos tokens que incluyen lo que el rol genera.
        'QUE CUENTA ESA METRICA: {}'.format(
            objetivo['objetivo'].get('explicacion')
            or 'no se ha explicado; deducelo del nombre con cuidado'),
        '',
        'GUARDIAS QUE NO PUEDEN EMPEORAR:',
    ]
    for guardia in objetivo.get('guardias') or []:
        limite = ('maximo {}'.format(guardia['maximo']) if 'maximo' in guardia
                  else 'minimo {}'.format(guardia.get('minimo')))
        lineas.append('- {} ({}), ahora en {}'.format(
            guardia['metrica'], limite, resumen['agregados'].get(guardia['metrica'])))
    lineas += ['', 'COMO VA AHORA EL PROMPT VIGENTE:']
    for nombre, valor in resumen['agregados'].items():
        lineas.append('- {}: {}'.format(nombre, valor))
    lineas += ['', 'DONDE LO HACE PEOR (casos del taller):']
    for peor in _peores(resumen, objetivo):
        lineas.append('- caso {}: {}'.format(
            peor['caso'], json.dumps(peor['medidas'], ensure_ascii=False)))
    lineas += [
        '', 'CUANTAS VARIANTES: {}'.format(cuantos),
        '', 'PROMPT VIGENTE, ENTERO Y TAL CUAL:', '', vigente,
    ]
    return '\n'.join(lineas)


def pedir_candidatos(objetivo, vigente, resumen, config, gasto, raiz='.', aviso=None):
    """Las variantes del prompt. Las escribe el optimizador, en ficheros.

    En ficheros y no en JSON porque un prompt son cientos de lineas de Markdown,
    y meterlo dentro de una cadena JSON lo convierte en algo que ni se lee ni se
    compara. Cada fichero es un prompt entero: no hay parches.
    """
    ajustes = (config.get('autoaprendizaje') or {})
    cuantos = int(ajustes.get('candidatos_por_ronda', 3))
    encargo = Path(raiz, OPTIMIZADOR)
    if not encargo.is_file():
        raise ErrorBanco('falta el encargo del optimizador en {}'.format(encargo))

    trabajo = tempfile.mkdtemp(prefix='banco-opt-')
    try:
        orden = [_ejecutable(config), '-p',
                 '--agents', json.dumps({AGENTE: {
                     'description': 'optimizador del banco',
                     'prompt': sin_frontmatter(encargo.read_text(encoding='utf-8')),
                     'tools': ['Write'],
                     'model': objetivo.get('modelo_optimizador') or 'opus'}},
                     ensure_ascii=False),
                 '--agent', AGENTE, '--output-format', 'json',
                 '--permission-mode', (config.get('lanzador') or {}).get(
                     'permisos', 'acceptEdits')]
        proceso = subprocess.run(
            orden, input=_encargo_optimizador(objetivo, vigente, resumen, cuantos),
            cwd=trabajo, text=True, capture_output=True, encoding='utf-8',
            errors='replace', timeout=ajustes.get('tope_segundos', 600) * 2)
        try:
            bruto = json.loads(proceso.stdout)
            gasto.suma(bruto.get('total_cost_usd'))
        except ValueError:
            raise ErrorBanco('el optimizador no devolvio JSON: {}'.format(
                (proceso.stderr or '')[:300]))

        candidatos = []
        for fichero in sorted(Path(trabajo).glob('*.md')):
            texto = fichero.read_text(encoding='utf-8', errors='replace').strip()
            if texto:
                candidatos.append({'nombre': fichero.stem, 'texto': texto})
        if not candidatos and aviso:
            aviso('el optimizador no escribio ninguna variante')
        return candidatos[:cuantos]
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


# --- la ronda -----------------------------------------------------------------

def _escribir(ruta, texto):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding='utf-8')


def _veredicto(ronda):
    lineas = ['# Ronda {}'.format(ronda['id']), '',
              '- objetivo: `{}`'.format(ronda['objetivo']),
              '- rol: `{}`'.format(ronda['rol']),
              '- modelo: `{}`'.format(ronda['modelo']),
              '- estado: **{}**'.format(ronda['estado']),
              '- gasto: {:.4f} $'.format(ronda['gasto']), '']
    if ronda.get('motivo'):
        lineas += ['> {}'.format(ronda['motivo']), '']
    lineas += ['## Taller', '', '| Prompt | {} | guardias |'.format(ronda['metrica']),
               '|---|---:|---|']
    for fila in ronda.get('taller') or []:
        lineas.append('| {} | {} | {} |'.format(
            fila['nombre'], fila['valor'], fila.get('guardias') or '-'))
    if ronda.get('reserva'):
        lineas += ['', '## Reserva', '',
                   '| Prompt | {} |'.format(ronda['metrica']), '|---|---:|']
        for fila in ronda['reserva']:
            lineas.append('| {} | {} |'.format(fila['nombre'], fila['valor']))
    if ronda.get('comparacion'):
        comparacion = ronda['comparacion']
        lineas += ['', '## Decision', '',
                   '- mejora: {}'.format(
                       '{:.1%}'.format(comparacion['ganancia'])
                       if comparacion.get('ganancia') is not None else 'no comparable'),
                   '- gana: {}'.format('si' if comparacion['gana'] else 'no')]
        for motivo in comparacion.get('motivos') or []:
            lineas.append('- {}'.format(motivo))
    return '\n'.join(lineas) + '\n'


def _git(raiz, *args):
    return subprocess.run(['git', '-C', str(raiz)] + list(args), text=True,
                          capture_output=True, encoding='utf-8', errors='replace')


def arbol_sucio(objetivo, raiz='.'):
    """Si hay trabajo sin commitear en lo que el banco puede pisar.

    El banco promueve commiteando, y la unica red debajo de una promocion
    automatica es poder revertir ese commit. Con cambios a medias dentro,
    revertir ya no devuelve el repositorio a donde estaba.
    """
    salida = _git(raiz, 'status', '--porcelain', '--', objetivo['prompt'])
    return bool((salida.stdout or '').strip())


def promover(objetivo, candidato, comparacion, ronda_id, raiz='.'):
    """Escribe el prompt ganador y lo commitea. Un fichero y nada mas."""
    destino = Path(raiz) / objetivo['prompt']
    _escribir(destino, candidato['texto'].rstrip() + '\n')
    mensaje = ('feat(banco): {} {} {:+.1%} en {}\n\n'
               'Promovido por el banco: {} casos de reserva, ronda {}.\n'
               'Se deshace revirtiendo este commit.').format(
        objetivo['rol'], comparacion['metrica'], -comparacion['ganancia'],
        objetivo['id'], comparacion.get('casos_reserva', '?'), ronda_id)
    _git(raiz, 'add', '--', objetivo['prompt'])
    resultado = _git(raiz, 'commit', '-m', mensaje)
    return {'fichero': objetivo['prompt'], 'commit': resultado.returncode == 0,
            'salida': (resultado.stdout or resultado.stderr or '').strip()[:300]}


def ronda(objetivo, config, gasto, numero, taller, reserva, raiz='.',
          seco=False, aviso=None, log=None):
    """Una vuelta entera: medir el vigente, proponer, medir, decidir."""
    decir = log or (lambda *_: None)
    ident = '{}-{}-{}'.format(datetime.now().strftime('%Y%m%d-%H%M'), objetivo['id'], numero)
    carpeta = Path(raiz, RONDAS, ident)
    vigente = prompt_vigente(objetivo, raiz)

    decir('  midiendo el prompt vigente sobre el taller ({} casos)'.format(len(taller)))
    prompt_v = componer(objetivo, vigente, raiz)
    resumen_v_taller = resumir(correr(prompt_v, taller, objetivo, config, gasto, aviso),
                               taller, objetivo, config)

    resultado = {'id': ident, 'objetivo': objetivo['id'], 'rol': objetivo['rol'],
                 'modelo': objetivo.get('modelo') or 'el de la sesion',
                 'metrica': objetivo['objetivo']['metrica'], 'estado': 'descartada',
                 'motivo': None, 'taller': [], 'reserva': [], 'comparacion': None,
                 # Caso a caso y metrica a metrica, que es lo que hay que poder
                 # mirar al dia siguiente: el agregado dice quien gano, y el
                 # detalle dice si gano por todos los casos o por uno raro.
                 'medidas': {'taller': {}, 'reserva': {}},
                 'gasto': gasto.total}

    def cerrar(estado, motivo=None):
        resultado['estado'] = estado
        resultado['motivo'] = motivo
        resultado['gasto'] = gasto.total
        _escribir(carpeta / 'veredicto.md', _veredicto(resultado))
        _escribir(carpeta / 'medidas.json',
                  json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
        return resultado

    resultado['taller'].append({'nombre': 'vigente',
                                'valor': resumen_v_taller['agregados'].get(resultado['metrica'])})
    resultado['medidas']['taller']['vigente'] = resumen_v_taller['detalle']
    if gasto.agotado:
        return cerrar('parada', 'se agoto el tope de gasto midiendo el vigente')

    decir('  pidiendo variantes al optimizador')
    candidatos = pedir_candidatos(objetivo, vigente, resumen_v_taller, config, gasto,
                                  raiz, aviso)
    if not candidatos:
        return cerrar('descartada', 'el optimizador no propuso nada')
    for candidato in candidatos:
        _escribir(carpeta / 'candidatos' / '{}.md'.format(candidato['nombre']),
                  candidato['texto'])

    mejor, mejor_resumen = None, None
    for candidato in candidatos:
        if gasto.agotado:
            return cerrar('parada', 'se agoto el tope de gasto midiendo candidatos')
        decir('  midiendo {} sobre el taller'.format(candidato['nombre']))
        resumen_c = resumir(
            correr(componer(objetivo, candidato['texto'], raiz), taller, objetivo,
                   config, gasto, aviso), taller, objetivo, config)
        comparacion = comparar(resumen_v_taller, resumen_c, objetivo, config)
        resultado['medidas']['taller'][candidato['nombre']] = resumen_c['detalle']
        resultado['taller'].append({
            'nombre': candidato['nombre'],
            'valor': resumen_c['agregados'].get(resultado['metrica']),
            'guardias': ', '.join('{} {}'.format(g['metrica'], 'ok' if g['pasa'] else 'NO')
                                  for g in comparacion['guardias'])})
        if all(g['pasa'] for g in comparacion['guardias']):
            ganancia = comparacion['ganancia']
            if ganancia is not None and (mejor is None or ganancia > mejor[1]):
                mejor, mejor_resumen = (candidato, ganancia), resumen_c

    if mejor is None:
        return cerrar('descartada', 'ningun candidato paso las guardias en el taller')

    candidato, ganancia_taller = mejor
    margen = (config.get('autoaprendizaje') or {}).get('margen_mejora', 0.1)
    if not merece_la_reserva(ganancia_taller, margen):
        return cerrar('descartada', 'el mejor del taller mejora {:.1%} y el margen'
                      ' es {:.1%}: no se gasta la reserva'.format(ganancia_taller, margen))
    decir('  el mejor del taller es {} ({:+.1%}). Midiendo en la reserva'.format(
        candidato['nombre'], ganancia_taller))
    if gasto.agotado:
        return cerrar('parada', 'se agoto el tope antes de la reserva')

    prompt_c = componer(objetivo, candidato['texto'], raiz)
    resumen_v_res = resumir(correr(prompt_v, reserva, objetivo, config, gasto, aviso),
                            reserva, objetivo, config)
    resumen_c_res = resumir(correr(prompt_c, reserva, objetivo, config, gasto, aviso),
                            reserva, objetivo, config)
    comparacion = comparar(resumen_v_res, resumen_c_res, objetivo, config)
    comparacion['casos_reserva'] = resumen_c_res['validas']
    resultado['comparacion'] = comparacion
    resultado['ganador'] = candidato['nombre']
    resultado['reserva'] = [
        {'nombre': 'vigente', 'valor': resumen_v_res['agregados'].get(resultado['metrica'])},
        {'nombre': candidato['nombre'],
         'valor': resumen_c_res['agregados'].get(resultado['metrica'])}]
    resultado['medidas']['reserva'] = {'vigente': resumen_v_res['detalle'],
                                       candidato['nombre']: resumen_c_res['detalle']}

    if not comparacion['gana']:
        return cerrar('descartada', '; '.join(comparacion['motivos']))
    if seco:
        return cerrar('descartada', 'ganaba, pero la corrida es en seco y no se promueve')

    resultado['promocion'] = promover(objetivo, candidato, comparacion, ident, raiz)
    return cerrar('promovida', 'gana por {:.1%} en la reserva'.format(comparacion['ganancia']))


def publicar(resultado, objetivo, trazas):
    """Manda la ronda a Langfuse: una traza, con sus numeros como puntuaciones.

    **No se usa el corredor de experimentos del SDK**, que tambien existe y
    tambien sabe recorrer un dataset. Dos motivos: no sabe parar cuando se acaba
    el presupuesto, que es la unica brida que tiene una promocion automatica, y
    tenerlo solo cuando hay red dejaria dos maneras de correr lo mismo. Una
    ronda se corre siempre igual, y esto la cuenta despues.
    """
    if trazas is None or not trazas.activa:
        return False
    metadata = {'objetivo': objetivo['id'], 'rol': objetivo['rol'],
                'ronda': resultado['id'], 'estado': resultado['estado'],
                'modelo': resultado['modelo'], 'banco': True}
    try:
        with trazas.traza('ronda-banco', tipo='span',
                          entrada={'taller': resultado['taller'],
                                   'reserva': resultado['reserva']},
                          sesion='banco-{}'.format(objetivo['id']),
                          etiquetas=('banco', objetivo['rol']),
                          metadata=metadata) as obs:
            obs.actualizar(output={'estado': resultado['estado'],
                                   'motivo': resultado['motivo'],
                                   'gasto_usd': resultado['gasto']})
            for fila in (resultado.get('reserva') or []):
                if fila.get('valor') is not None:
                    obs.nota('{}-{}'.format(resultado['metrica'], fila['nombre']),
                             fila['valor'])
            comparacion = resultado.get('comparacion') or {}
            if comparacion.get('ganancia') is not None:
                obs.nota('mejora', comparacion['ganancia'],
                         comentario='; '.join(comparacion.get('motivos') or []) or None)
            obs.nota('promovida', bool(resultado['estado'] == 'promovida'))
    except Exception:
        return False
    return True


def aprender(objetivo, config, raiz='.', seco=False, rondas=None, trazas=None,
             aviso=None, log=None):
    """El loop entero. Para al promover, al agotarse o al quedarse sin margen."""
    decir = log or (lambda *_: None)
    ajustes = (config.get('autoaprendizaje') or {})
    if not seco and arbol_sucio(objetivo, raiz):
        raise ErrorBanco(
            'hay cambios sin commitear en {}. El banco promueve commiteando, y'
            ' esa es toda la red que tiene una promocion automatica: con trabajo'
            ' a medias dentro, revertir el commit ya no deja el repositorio como'
            ' estaba.'.format(objetivo['prompt']))

    taller, origen_t = casos_mod.cargar(objetivo, 'taller', trazas, aviso=aviso)
    reserva, origen_r = casos_mod.cargar(objetivo, 'reserva', trazas, aviso=aviso)
    if not taller or not reserva:
        raise ErrorBanco(
            'no hay casos para {}. Siembra el dataset primero:'
            ' python -m novela sembrar --objetivo {}'.format(objetivo['id'], objetivo['id']))
    decir('casos: {} de taller y {} de reserva ({} / {})'.format(
        len(taller), len(reserva), origen_t, origen_r))

    minimos = ajustes.get('casos_minimos', 4)
    if len(reserva) < minimos:
        decir('aviso: la reserva tiene {} casos y el suelo es {}. Se puede medir,'
              ' pero ninguna promocion sera valida.'.format(len(reserva), minimos))

    gasto = Gasto(ajustes.get('gasto_max', 5.0))
    tope = int(rondas or ajustes.get('rondas_max', 5))
    paciencia = int(ajustes.get('paciencia', 2))
    sin_mejorar, hechas = 0, []

    for numero in range(1, tope + 1):
        decir('ronda {} de {}'.format(numero, tope))
        resultado = ronda(objetivo, config, gasto, numero, taller, reserva, raiz,
                          seco=seco, aviso=aviso, log=decir)
        hechas.append(resultado)
        publicar(resultado, objetivo, trazas)
        decir('  {}: {}'.format(resultado['estado'], resultado['motivo'] or ''))
        if resultado['estado'] == 'promovida':
            break
        if resultado['estado'] == 'parada':
            break
        gano_algo = any(f.get('valor') is not None for f in resultado['taller'][1:])
        sin_mejorar = 0 if gano_algo and resultado.get('comparacion') else sin_mejorar + 1
        if sin_mejorar >= paciencia:
            resultado['estado'] = 'agotada'
            decir('  {} rondas seguidas sin acercarse. Se para.'.format(sin_mejorar))
            break

    return {'rondas': hechas, 'gasto': gasto.total,
            'estado': hechas[-1]['estado'] if hechas else 'agotada'}
