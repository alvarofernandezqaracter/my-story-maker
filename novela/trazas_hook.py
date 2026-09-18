# §20 + §21 Trazas en vivo del camino delegado.
#
# `trazas_cc.py` reconstruye el arbol desde el canon cuando ya todo ha pasado, y
# su cabecera dice lo que le falta: "no hay latencia, ni tokens, ni coste, ni el
# prompt exacto: eso solo lo tiene quien hizo la llamada". Este fichero es quien
# hizo la llamada.
#
# El punto unico de instrumentacion que §21 daba por perdido existe, y es el
# hook `PostToolUse` de Claude Code sobre el tool `Agent`: por ahi pasan las
# ocho llamadas a subagentes y ninguna otra cosa. El resultado del tool trae el
# prompt entero, la respuesta, el modelo que resolvio, la duracion y el reparto
# de tokens con su cache: todo lo que hace falta para saber lo que costo una
# llamada, sin tener que ser quien la hizo.
#
# **Nada de esto puede parar una novela**, que es la regla de §20 y aqui pesa
# mas que en ningun otro sitio: un hook que revienta ensucia la sesion del
# orquestador.
# Por eso todo va envuelto, la salida siempre es 0 y cada llamada deja ademas su
# linea en un diario local, que sobrevive aunque Langfuse no conteste.
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .afinado import ruta_vuelta, vuelta_en_curso
from .biblioteca import actual as novela_actual
from .canon_cc import CanonCC
from .trazas import (
    GENERACIONES, id_de_traza, reparto_de_tokens, sesion_de, Trazas)
from .trazas_cc import _config_de_trazas

# El tool con el que una sesion de Claude Code llama a un subagente. Se
# comprueba el nombre porque el hook podria estar puesto sobre un matcher mas
# ancho: lo que no sea esto no se traza.
TOOL = 'Agent'

# Los ocho de §21 traducidos a los seis roles de §5, que es como los nombra §20.
# Los tres validadores comparten nombre de observacion y se distinguen por su
# dimension, como en §20: asi una nota de continuidad se compara
# entre los dos caminos sin tener que traducir nada.
ROLES = {
    'novela-investigador': ('investigador', None),
    'novela-arquitecto': ('arquitecto', None),
    'novela-escritor': ('escritor', None),
    'novela-validador-continuidad': ('validador', 'continuidad'),
    'novela-validador-anacronismos': ('validador', 'anacronismos'),
    'novela-validador-logica-ritmo': ('validador', 'logica_ritmo'),
    'novela-cronista': ('cronista', None),
    'novela-editor-global': ('editor_global', None),
}

# Los roles que no son de un capitulo: los dos de la preparacion y el del
# cierre. El resto vive dentro del loop de §8 y lleva capitulo.
TRAMO_FIJO = {
    'investigador': ('preparar', 'preparar-novela'),
    'arquitecto': ('preparar', 'preparar-novela'),
    'editor_global': ('cerrar', 'cerrar-novela'),
}

CAPITULO = re.compile(r'cap(?:itulo)?[\s\-_]*0*(\d{1,3})', re.IGNORECASE)
INTENTO = re.compile(r'intento[\s\-_]*0*(\d{1,3})', re.IGNORECASE)

DIARIO = 'trazas/llamadas.jsonl'

ETIQUETAS = ('delegado', 'directo')

# Como dice el tool que fue bien. Son varias porque el nombre no es nuestro y ha
# cambiado ya una vez: lo que no este aqui se marca como aviso en la traza, que
# es preferible a dar por bueno un fallo.
ESTADOS_BUENOS = ('success', 'completed', 'ok', 'desconocido')


def _texto_de(valor, tope=200000):
    """Lo que sea a texto, para poder buscar el capitulo dentro."""
    if valor is None:
        return ''
    if isinstance(valor, str):
        return valor[:tope]
    try:
        return json.dumps(valor, ensure_ascii=False, default=str)[:tope]
    except (TypeError, ValueError):
        return str(valor)[:tope]


def situar(rol, texto):
    """De que tramo es esta llamada, y de que capitulo e intento.

    Sale del texto de la llamada y no del canon a proposito: cuando el hook
    corre, el orquestador todavia no ha escrito en `estado.json` el intento que
    acaba de empezar. Las rutas que se le pasan al subagente -`cap-04.md`,
    `cap-04-intento-2.md`- si lo dicen ya.
    """
    fijo = TRAMO_FIJO.get(rol)
    if fijo:
        return {'tramo': fijo[0], 'traza': fijo[1], 'capitulo': None, 'intento': None}

    numeros = CAPITULO.findall(texto or '')
    capitulo = int(numeros[0]) if numeros else None
    intentos = INTENTO.findall(texto or '')
    intento = int(intentos[0]) if intentos else None
    if capitulo is None:
        # Sin capitulo no hay donde colgarla. Se traza igual, en su propia
        # traza, y se marca: perder la llamada seria peor que perder el arbol.
        return {'tramo': 'sin-capitulo', 'traza': 'escribir-capitulo',
                'capitulo': None, 'intento': intento}
    return {'tramo': 'cap-{:02d}'.format(capitulo), 'traza': 'escribir-capitulo',
            'capitulo': capitulo, 'intento': intento}


def _anotar(raiz, linea):
    """El diario local. Se escribe pase lo que pase con Langfuse.

    No guarda el prompt ni la respuesta -los tiene Langfuse y los tiene el
    transcript de la sesion-, solo lo que se cuenta: quien, cuando, cuanto
    tardo y cuantos tokens costo. Sirve para cuadrar un informe sin red y para
    saber que una llamada existio aunque su traza no llegara.
    """
    try:
        ruta = Path(raiz) / DIARIO
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open('a', encoding='utf-8') as f:
            f.write(json.dumps(linea, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _perfil(ruta='config.json'):
    """El perfil, leido con tolerancia.

    `cargar_config` valida entero y para si algo no cuadra (§12), que es lo
    correcto para un comando y lo contrario de lo que quiere un hook: aqui una
    coma de mas en un umbral que no me incumbe no puede tumbar la observacion.
    """
    try:
        return json.loads(Path(ruta).read_text(encoding='utf-8'))
    except Exception:
        return {}


def _con_entorno(perfil, entorno):
    """El mismo perfil con otro entorno de trazas, sin tocar el fichero.

    El entorno lo elige el perfil (§12) y aqui no se inventa ninguno: se cambia
    por el que la vuelta abierta trae escrito, que salio de `afinado.entorno`.
    """
    if not entorno:
        return perfil
    bloque = dict((perfil or {}).get('trazas') or {})
    bloque['entorno'] = entorno
    return dict(perfil or {}, trazas=bloque)


def procesar(payload, raiz=None, ruta_config='config.json', momento=None):
    """Una llamada a un subagente, observada. Devuelve que se hizo y por que no.

    `momento` es cuando termino la llamada. En vivo es ahora y no hace falta
    decirlo; leyendo un transcript de hace tres dias, no.
    """
    if (payload.get('tool_name') or '') != TOOL:
        return {'trazado': False, 'motivo': 'no es una llamada al tool {}'.format(TOOL)}

    # Los hooks tambien corren dentro de un subagente. Si esta llamada la hizo
    # uno, no es del orquestador y no entra en el arbol de §20.
    if payload.get('agent_id'):
        return {'trazado': False, 'motivo': 'la llamada viene de dentro de un subagente'}

    entrada = payload.get('tool_input') or {}
    subagente = entrada.get('subagent_type') or ''
    if subagente not in ROLES:
        # Ajeno al reparto, pero **no se calla**. Si un subagente `novela-*` no
        # carga, el orquestador puede sustituirlo por uno generico y seguir: la
        # novela sale, y el rol desaparece de la observacion sin que nadie lo
        # note. Las cifras de ese rol quedan por debajo de las reales y parecen
        # buenas. Por eso la llamada ajena deja su linea en el diario: no entra
        # en el arbol de §20 -no es una unidad de trabajo del sistema-, pero
        # queda constancia de que hubo trabajo que el arbol no vio.
        linea = {
            'momento': (momento or datetime.now(timezone.utc)).isoformat(),
            'ajeno': True,
            'subagente': subagente or None,
            'descripcion': entrada.get('description') or None,
            'sesion_cc': payload.get('session_id'),
        }
        _anotar(raiz, linea)
        return {'trazado': False, 'diario': True, 'linea': linea,
                'motivo': 'subagente ajeno a la novela: {}'.format(
                    subagente or 'sin tipo')}

    rol, dimension = ROLES[subagente]
    respuesta = payload.get('tool_response')
    respuesta = respuesta if isinstance(respuesta, dict) else {'content': respuesta}

    prompt = entrada.get('prompt') or respuesta.get('prompt') or ''
    salida = respuesta.get('content')
    sitio = situar(rol, '\n'.join([_texto_de(prompt), entrada.get('description') or '',
                                   _texto_de(salida, 20000)]))

    duracion = respuesta.get('totalDurationMs')
    estado = respuesta.get('status') or 'desconocido'
    marca = momento or datetime.now(timezone.utc)
    linea = {
        'momento': marca.isoformat(),
        'rol': rol,
        'dimension': dimension,
        'subagente': subagente,
        'tramo': sitio['tramo'],
        'capitulo': sitio['capitulo'],
        'intento': sitio['intento'],
        'modelo': respuesta.get('resolvedModel'),
        'estado': estado,
        'duracion_ms': duracion,
        'tokens': respuesta.get('totalTokens'),
        'reparto': reparto_de_tokens(respuesta.get('usage')),
        'herramientas': respuesta.get('totalToolUseCount'),
        'sesion_cc': payload.get('session_id'),
    }

    # Mientras hay una vuelta de afinado abierta, esta llamada no es de ninguna
    # novela y no puede colgarse de su sesion (AFINADO.md §6). No es una
    # precaucion teorica: el trabajo anterior metio veintiuna observaciones de
    # prueba dentro de la sesion de una novela real, y quien la consultara
    # despues contaba el doble de llamadas de las que hubo.
    perfil = _perfil(ruta_config)
    vuelta = vuelta_en_curso()
    if vuelta:
        raiz = ruta_vuelta(vuelta['vuelta'])
        sesion = vuelta['sesion']
        sitio = dict(sitio, tramo='afinado', traza='afinar-prompt')
        linea['tramo'] = sitio['tramo']
        linea['vuelta'] = vuelta['vuelta']
        perfil = _con_entorno(perfil, vuelta.get('entorno'))
    else:
        canon = CanonCC(raiz)
        sesion = sesion_de(canon.brief()) if canon.existe else None

    trace_id = id_de_traza('{}|{}'.format(sesion or 'sin-sesion', sitio['tramo']))
    linea['sesion'] = sesion
    linea['traza'] = trace_id
    _anotar(raiz, linea)

    trazas = Trazas(_config_de_trazas(perfil))
    if not trazas.activa:
        return {'trazado': False, 'motivo': trazas.motivo, 'diario': True, 'linea': linea}

    metadata = {
        'camino': 'delegado', 'origen': 'hook', 'directo': True,
        'subagente': subagente, 'capitulo': sitio['capitulo'],
        'intento': sitio['intento'], 'dimension': dimension,
        'duracion_ms': duracion, 'herramientas': respuesta.get('totalToolUseCount'),
        'tokens_totales': respuesta.get('totalTokens'),
        'estado': estado, 'sesion_cc': payload.get('session_id'),
        'agente_cc': respuesta.get('agentId'),
        # La duracion real, que es lo unico que no se puede reponer despues: la
        # marca de tiempo del span es la de este proceso, no la de la llamada.
        'empezo': (marca - timedelta(milliseconds=duracion)).isoformat()
        if isinstance(duracion, (int, float)) else None,
        'termino': marca.isoformat(),
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    # El arbol es el mismo de §20: una observacion `agent`
    # -el rol trabajando- con una `generation` dentro -la invocacion del modelo-.
    # No es simetria por gusto: Langfuse solo contabiliza modelo, tokens y coste
    # en una `generation`, y colgarlos de la `agent` los tira sin avisar.
    reparto = reparto_de_tokens(respuesta.get('usage'))
    modelo = respuesta.get('resolvedModel')
    try:
        with trazas.traza(rol, tipo='agent', entrada=prompt, sesion=sesion,
                          etiquetas=ETIQUETAS, metadata=metadata,
                          trace_id=trace_id, nombre_traza=sitio['traza']) as obs:
            obs.actualizar(output=salida)
            if estado not in ESTADOS_BUENOS:
                obs.actualizar(level='WARNING', status_message='estado {}'.format(estado))
            with trazas.paso(GENERACIONES.get(rol, 'llamar-agente'), 'generation',
                             entrada=prompt, metadata=metadata, modelo=modelo) as gen:
                gen.actualizar(output=salida, usage_details=reparto)
    finally:
        trazas.cerrar()

    if not trazas.activa:
        return {'trazado': False, 'motivo': trazas.motivo, 'diario': True, 'linea': linea}
    return {'trazado': True, 'motivo': None, 'linea': linea, 'traza': trace_id}


def desde_stdin(flujo=None, raiz=None, ruta_config='config.json'):
    """Entrada del hook. **Nunca lanza y siempre devuelve 0.**

    Un `PostToolUse` no puede bloquear nada -el tool ya corrio-, pero un proceso
    que revienta escribe en el log de la sesion y distrae a quien orquesta. La
    unica salida legitima de aqui es cero.
    """
    try:
        crudo = (flujo or sys.stdin).read()
        payload = json.loads(crudo) if crudo.strip() else {}
        raiz = raiz or os.environ.get('NOVELA_RAIZ_CC') or novela_actual()
        resultado = procesar(payload, raiz=raiz, ruta_config=ruta_config)
        # Sale por stdout, que en un PostToolUse va al log de depuracion y no a
        # la conversacion: se puede leer con --debug sin ensuciar la sesion.
        sys.stdout.write(json.dumps(resultado, ensure_ascii=False, default=str) + '\n')
    except Exception as e:
        try:
            sys.stdout.write(json.dumps({'trazado': False, 'motivo': str(e)}) + '\n')
        except Exception:
            pass
    return 0
