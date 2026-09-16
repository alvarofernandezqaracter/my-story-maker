# Modo de ejecucion claude_code (§12): las llamadas no salen contra la API de
# Anthropic sino contra la CLI de Claude Code instalada en la maquina, en modo
# headless (claude --print). La credencial es la sesion de la propia CLI, asi
# que este modo corre sin ANTHROPIC_API_KEY en el entorno y sin SDK instalado.
#
# El contrato es el del modo real y no cambia nada aguas arriba: mismas
# instrucciones de §10, misma peticion de un unico objeto JSON y misma politica
# de §13 ante el fallo (un reintento y parar), que vive en agentes.py.
import json
import os
import shutil
import subprocess
import tempfile

from .proveedor import extraer_json, instruccion_de_formato

# Transporte, no criterio: lo que tarda como mucho una llamada antes de darla
# por perdida. Los umbrales que deciden algo viven en config.json.
TIMEOUT_S = 900

# El agente solo tiene que devolver un JSON: va sin herramientas, sin MCP, sin
# skills de la CLI y sin persistir sesion. Y corre en un directorio vacio para
# que no se le cuele el CLAUDE.md del repo como contexto.
BANDERAS = [
    '--print',
    '--output-format', 'json',
    '--exclude-dynamic-system-prompt-sections',
    '--tools', '',
    '--permission-prompts', 'none',
    '--strict-mcp-config',
    '--disable-slash-commands',
    '--no-session-persistence',
    '--effort', 'high',
    '--max-turns', '1',
]


def _ejecutable():
    ruta = shutil.which('claude')
    if not ruta:
        raise RuntimeError(
            'el modo claude_code necesita la CLI de Claude Code en el PATH')
    return ruta


def llamar_a_claude_code(rol, modelo, instrucciones, entrada):
    """Una llamada a un agente resuelta por la CLI de Claude Code."""
    sistema = instrucciones + instruccion_de_formato(rol)
    peticion = json.dumps(entrada, indent=2, ensure_ascii=False)

    with tempfile.TemporaryDirectory(prefix='novela-{}-'.format(rol)) as vacio:
        fichero_sistema = os.path.join(vacio, 'sistema.txt')
        with open(fichero_sistema, 'w', encoding='utf-8') as f:
            f.write(sistema)

        orden = [_ejecutable()] + BANDERAS + [
            '--model', modelo,
            '--system-prompt-file', fichero_sistema,
        ]
        try:
            completado = subprocess.run(
                orden, input=peticion, cwd=vacio, capture_output=True,
                text=True, encoding='utf-8', timeout=TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                'la CLI de Claude Code no respondio en {} s en el rol {}'.format(
                    TIMEOUT_S, rol)) from e

    if completado.returncode != 0:
        detalle = (completado.stderr or completado.stdout or '').strip()
        raise RuntimeError('la CLI de Claude Code fallo en el rol {}: {}'.format(
            rol, detalle[:500]))

    try:
        sobre = json.loads(completado.stdout)
    except ValueError as e:
        raise RuntimeError(
            'la CLI de Claude Code no devolvio JSON en el rol {}: {}'.format(rol, e)) from e

    if sobre.get('is_error') or sobre.get('subtype') != 'success':
        raise RuntimeError('la CLI de Claude Code no completo el rol {}: {}'.format(
            rol, sobre.get('result') or sobre.get('subtype')))

    return {'salida': extraer_json(sobre.get('result') or ''), 'uso': sobre.get('usage')}
