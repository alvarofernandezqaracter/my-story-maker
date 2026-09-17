# §21 Lector del transcript de una sesion de Claude Code.
#
# El hook de `trazas_hook.py` observa las llamadas segun pasan, pero solo desde
# que esta puesto. Las novelas escritas antes no estan perdidas: Claude Code
# guarda cada sesion en un JSONL bajo `~/.claude/projects/<proyecto>/`, y ahi
# esta cada llamada al tool `Agent` con **exactamente** el mismo contenido que
# recibe el hook -el prompt, la respuesta, el modelo, la duracion y el reparto
# de tokens-, ademas de la hora real a la que ocurrio.
#
# Por eso esto no traza: reconstruye el payload del hook y se lo pasa a
# `procesar`. Un solo camino de codigo para lo de ahora y para lo de antes; si
# cambia como se observa una llamada, cambia para las dos cosas a la vez.
import json
import os
from datetime import datetime
from pathlib import Path

from .trazas_hook import procesar, ROLES, TOOL

PROYECTOS = Path.home() / '.claude' / 'projects'


def slug_de(ruta):
    """El nombre con el que Claude Code guarda un proyecto.

    Es la ruta absoluta con los separadores y los espacios convertidos en
    guiones y la unidad en minuscula. Se comprueba contra el disco antes de
    usarlo, porque esta regla es de la herramienta y no nuestra.
    """
    texto = str(Path(ruta).resolve())
    if len(texto) > 1 and texto[1] == ':':
        texto = texto[0].lower() + texto[1:]
    for sobra in (':', '\\', '/', ' ', '_'):
        texto = texto.replace(sobra, '-')
    return texto


def _cwd_de(fichero):
    """El directorio de trabajo que declara un transcript, de su primera linea."""
    try:
        with open(fichero, encoding='utf-8') as f:
            for linea in f:
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get('cwd'):
                    return d['cwd']
    except OSError:
        pass
    return None


def directorio_de(raiz_repo, proyectos=None):
    """Donde estan los transcripts de este repositorio.

    Primero por el nombre, que es barato. Si no acierta -la regla del slug es de
    Claude Code y puede cambiar-, se buscan por el `cwd` que cada transcript
    declara dentro, que es la fuente de verdad y no depende de ninguna regla.
    """
    base = Path(proyectos or PROYECTOS)
    if not base.exists():
        return None
    esperado = base / slug_de(raiz_repo)
    if esperado.exists():
        return esperado

    objetivo = str(Path(raiz_repo).resolve()).lower()
    for candidato in sorted(base.iterdir()):
        if not candidato.is_dir():
            continue
        for fichero in candidato.glob('*.jsonl'):
            cwd = _cwd_de(fichero)
            if cwd and str(Path(cwd)).lower() == objetivo:
                return candidato
            break
    return None


def _momento(texto):
    if not texto:
        return None
    try:
        return datetime.fromisoformat(str(texto).replace('Z', '+00:00'))
    except ValueError:
        return None


def llamadas(directorio):
    """Las llamadas a subagentes de la novela, en orden, como payloads de hook.

    Una llamada son dos lineas del JSONL separadas entre si: el `tool_use` del
    orquestador y el `tool_result` que vuelve. Se emparejan por el id del tool,
    y solo sale lo que ademas trae `toolUseResult`, que es donde viven los
    tokens y la duracion.
    """
    pendientes = {}
    encontradas = []
    for fichero in sorted(Path(directorio).glob('*.jsonl')):
        try:
            lineas = open(fichero, encoding='utf-8')
        except OSError:
            continue
        with lineas:
            for linea in lineas:
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                contenido = (d.get('message') or {}).get('content')
                if not isinstance(contenido, list):
                    continue
                for bloque in contenido:
                    if not isinstance(bloque, dict):
                        continue
                    if bloque.get('type') == 'tool_use' and bloque.get('name') == TOOL:
                        entrada = bloque.get('input') or {}
                        if entrada.get('subagent_type') in ROLES:
                            pendientes[bloque.get('id')] = (entrada, d.get('sessionId'))
                    elif bloque.get('type') == 'tool_result':
                        clave = bloque.get('tool_use_id')
                        if clave not in pendientes:
                            continue
                        entrada, sesion_cc = pendientes.pop(clave)
                        resultado = d.get('toolUseResult')
                        if not isinstance(resultado, dict):
                            continue
                        momento = _momento(d.get('timestamp'))
                        encontradas.append((momento, {
                            'hook_event_name': 'PostToolUse',
                            'tool_name': TOOL,
                            'tool_use_id': clave,
                            'session_id': sesion_cc,
                            'tool_input': entrada,
                            'tool_response': resultado,
                        }))
    # En orden de llegada: las trazas se leen por tiempo y un capitulo 6 antes
    # que un capitulo 1 no se entiende.
    encontradas.sort(key=lambda par: (par[0] is None, par[0]))
    return encontradas


def exportar(raiz_repo='.', raiz_cc=None, ruta_config='config.json',
             proyectos=None, aviso=None):
    """Manda a Langfuse lo que el transcript sabe de las llamadas ya hechas."""
    directorio = directorio_de(raiz_repo, proyectos)
    if not directorio:
        return {'enviado': False,
                'motivo': 'no encuentro los transcripts de este repositorio en {}'.format(
                    Path(proyectos or PROYECTOS).as_posix())}

    encontradas = llamadas(directorio)
    if not encontradas:
        return {'enviado': False, 'motivo': 'no hay llamadas a subagentes de la novela',
                'directorio': directorio.as_posix()}

    trazadas = 0
    motivos = []
    for momento, payload in encontradas:
        argumentos = {'ruta_config': ruta_config, 'momento': momento}
        if raiz_cc:
            argumentos['raiz'] = raiz_cc
        resultado = procesar(payload, **argumentos)
        if resultado.get('trazado'):
            trazadas += 1
        elif resultado.get('motivo'):
            motivos.append(resultado['motivo'])
            if aviso:
                aviso(resultado['motivo'])

    return {'enviado': trazadas > 0, 'llamadas': len(encontradas), 'trazadas': trazadas,
            'directorio': directorio.as_posix(),
            'motivo': motivos[0] if motivos and not trazadas else None}
