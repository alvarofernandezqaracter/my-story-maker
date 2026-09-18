# §19 El lanzador. Arranca una sesion de Claude Code sobre este repositorio con
# el brief que se ha tecleado en la pagina, y se aparta.
#
# **Esto no rompe la primera regla de §21, y conviene ver por que.** Esa regla
# dice que en el canon escribe el orquestador y nadie mas. Aqui no se escribe ni
# un byte del canon: lo que se hace es arrancar al orquestador y dejar que
# escriba el. Lo que si cambia es el invariante de §19 -que ningun metodo
# distinto de GET hacia nada-, y cambia en una sola ruta, acotada a esto.
#
# El proceso queda suelto a proposito. Escribir una novela son muchos minutos y
# muchas llamadas, y la peticion HTTP que lo arranca no se va a quedar esperando
# a que acabe: la pagina ve el avance como lo ve siempre, releyendo el canon.
import os
import subprocess
import sys
from pathlib import Path

from .biblioteca import crear as crear_novela, RAIZ as BIBLIOTECA

CAMPOS = ('epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo')

# Los modos de permiso que entiende Claude Code. `acceptEdits` es el que trae el
# config del repositorio: una sesion sin terminal delante no puede contestar a
# una pregunta de permisos, asi que sin esto la novela se queda parada en la
# primera escritura. No se pone `bypassPermissions` por defecto porque eso es
# una decision de quien opera la maquina, no de este fichero.
PERMISOS = ('default', 'acceptEdits', 'bypassPermissions', 'plan')

# Donde va lo que el proceso imprima. No es canon y nada lo vuelve a leer como
# dato: esta para poder mirar por que no arranco algo que no arranco.
LOG = 'lanzamiento.log'


class ErrorLanzador(Exception):
    """El brief no sirve, o no hay forma de arrancar."""


# Un solo lanzamiento a la vez por servidor. Es estado del proceso, no del libro:
# el del libro vive en el canon (§13) y este se muere con el servidor, que es lo
# correcto porque describe algo que solo existe mientras el servidor existe.
_proceso = None
_ultimo = None


def validar(bruto):
    """Los cinco campos de §3, con el mismo criterio con el que los pide la skill.

    Devuelve el brief normalizado. La comprobacion de verdad -la de los VD-xx-
    la hace el orquestador antes de escribir, que es donde significa algo; esto
    solo evita mandarle una sesion entera a por un campo vacio.
    """
    if not isinstance(bruto, dict):
        raise ErrorLanzador('el brief tiene que ser un objeto con los cinco campos')

    brief = {}
    faltan = []
    for campo in CAMPOS:
        valor = bruto.get(campo)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            faltan.append(campo)
            continue
        brief[campo] = valor.strip() if isinstance(valor, str) else valor
    if faltan:
        raise ErrorLanzador(
            'faltan campos del brief y ninguno tiene valor por defecto (§3): '
            + ', '.join(faltan))

    for campo in ('capitulos', 'palabras_por_capitulo'):
        try:
            brief[campo] = int(str(brief[campo]).strip())
        except (TypeError, ValueError):
            raise ErrorLanzador('{} tiene que ser un numero entero'.format(campo)) from None
        if brief[campo] < 1:
            raise ErrorLanzador('{} tiene que ser mayor que cero'.format(campo))

    return brief


def prompt(brief, destino):
    """El mensaje con el que arranca la sesion: donde escribir, y los cinco campos.

    La carpeta va delante porque es lo primero que el orquestador necesita saber:
    no hay carpeta de trabajo fija, cada novela vive en la suya desde que nace
    (§21), y esa es la razon de que empezar un libro ya no pise el anterior.

    Va como un solo argumento de la linea de ordenes, nunca por un shell, asi que
    lo que se teclee en la pagina no puede convertirse en otra orden.
    """
    lineas = ['/orquestar-novela preparar y escribir la novela entera.',
              '',
              'La carpeta de esta novela es {}. Escribe ahi el canon, los'
              ' capitulos y el paquete de contexto, y no en ninguna otra.'.format(destino),
              '',
              'Brief:']
    for campo in CAMPOS:
        lineas.append('{}: {}'.format(campo, brief[campo]))
    return '\n'.join(lineas)


def _vivo():
    return _proceso is not None and _proceso.poll() is None


def estado():
    """Que hay corriendo, si es que hay algo. No mira el canon: eso es otra cosa."""
    if _vivo():
        return {'corriendo': True, 'pid': _proceso.pid, 'lanzado': _ultimo}
    salida = _proceso.returncode if _proceso is not None else None
    return {'corriendo': False, 'pid': None, 'lanzado': _ultimo, 'salida': salida}


def lanzar(bruto, config, raiz='.'):
    """Arranca `claude -p` con el brief y devuelve lo que se ha arrancado."""
    global _proceso, _ultimo

    if _vivo():
        raise ErrorLanzador(
            'ya hay una sesion corriendo (pid {}). Una novela a la vez: son'
            ' muchas llamadas y dos a la vez se estorban en cuota antes que en'
            ' disco (§21)'.format(_proceso.pid))

    brief = validar(bruto)

    # La novela nace ya en su sitio definitivo. Aqui se aparta la carpeta y nada
    # mas: dentro escribe el orquestador y nadie mas, que es la primera regla de
    # §21, y un directorio vacio no es canon.
    raiz = Path(raiz).resolve()
    novela = crear_novela(brief, raiz=(raiz / BIBLIOTECA).as_posix())
    destino = Path(novela['ruta'])

    ajustes = config.get('lanzador', {})
    orden = [
        ajustes.get('comando', 'claude'),
        '-p', prompt(brief, '{}/{}'.format(BIBLIOTECA, novela['nombre'])),
        '--permission-mode', ajustes.get('permisos', 'acceptEdits'),
    ]

    ruta_log = destino / LOG

    # En Windows, el servidor y el hijo comparten grupo de procesos: un Ctrl+C
    # sobre la interfaz se llevaria por delante la novela a medio escribir.
    extras = {}
    if sys.platform == 'win32':
        extras['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        extras['start_new_session'] = True

    try:
        registro = open(ruta_log, 'w', encoding='utf-8')
        _proceso = subprocess.Popen(
            orden, cwd=str(raiz), stdin=subprocess.DEVNULL,
            stdout=registro, stderr=subprocess.STDOUT, **extras)
    except OSError as e:
        raise ErrorLanzador(
            'no se pudo arrancar "{}": {}. El lanzador necesita el CLI de Claude'
            ' Code en el PATH; si esta en otro sitio, ponlo en lanzador.comando'
            .format(orden[0], e)) from e

    _ultimo = {
        'pid': _proceso.pid,
        'brief': brief,
        'novela': novela['nombre'],
        'carpeta': novela['ruta'],
        'log': os.path.relpath(ruta_log, raiz).replace('\\', '/'),
        'permisos': orden[-1],
    }
    return dict(_ultimo, corriendo=True)
