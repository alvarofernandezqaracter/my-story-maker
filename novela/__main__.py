# CLI. Ningun comando escribe una novela: eso lo hace una sesion de Claude Code
# con la skill `orquestar-novela` (§21). Lo que hay aqui es lo que rodea a esa
# conversacion y no cabe dentro de ella: la interfaz para mirar el canon, y las
# trazas para saber lo que costo.
#
# El estado vive en el canon, nunca aqui (§13). Por eso ningun comando de estos
# toma argumentos de posicion salvo el suyo propio.
import json
import sys
from pathlib import Path

from .config import cargar_config, ErrorConfig
from .entorno import cargar_entorno
from .informe import construir as construir_informe, texto as texto_informe
from .servidor import arrancar as arrancar_interfaz
from .transcripcion import exportar as exportar_transcript
from .trazas_cc import exportar as exportar_trazas_cc
from .trazas_hook import desde_stdin as trazar_desde_stdin

AYUDA = """
novela — utilidades del sistema de novelas historicas

La novela se escribe desde Claude Code: abre el repositorio y lanza
/orquestar-novela (§21). Lo de aqui es lo que mira ese trabajo por fuera.

  novela ui [--puerto N]           interfaz web en el navegador (§19). Mira el
                                   canon de novela-cc/ y no escribe en el
  novela trazar [--modelo M]       manda a Langfuse el canon de novela-cc/,
                                   reconstruido (§20)
  novela trazar --transcript       lo mismo pero desde el transcript de la
                                   sesion: con prompt, tokens, modelo y latencia
  novela hook-traza                lee un PostToolUse por stdin y traza la
                                   llamada al subagente. Lo llama el hook (§22)
  novela informe-trazas [--sesion S] [--salida F] [--json]
                                   lee de vuelta las trazas de una novela y
                                   agrega el gasto para analizarlo (§22)

Opciones globales: --config <ruta> (por defecto config.json)
""".strip()


def _parsear(argv):
    posicionales = []
    opciones = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith('--'):
            clave = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                i += 1
                opciones[clave] = argv[i]
            else:
                opciones[clave] = True
        else:
            posicionales.append(a)
        i += 1
    return posicionales, opciones


def _log(*partes):
    sys.stdout.write('{}\n'.format(' '.join(str(p) for p in partes)))


def _entero(valor, mensaje):
    try:
        return int(str(valor))
    except (TypeError, ValueError):
        raise ValueError(mensaje) from None


def _aviso(mensaje):
    sys.stderr.write('trazas: {}\n'.format(mensaje))


def _ejecutar(comando, posicionales, opciones, config):
    if comando == 'ui':
        # La interfaz mira y no toca: en el canon de §21 escribe el orquestador
        # y nadie mas, y no hay aqui ningun motor que pueda arrancar nada.
        arrancar_interfaz(
            config,
            puerto=_entero(opciones['puerto'], 'ui --puerto necesita un numero')
            if opciones.get('puerto') else None,
            abrir=not opciones.get('sin-navegador'),
            log=_log)

    elif comando == 'trazar':
        # Quien orquesta es una sesion de Claude Code, asi que no hay una capa
        # de agentes en la que interceptar la llamada. Quedan dos maneras de
        # llegar a Langfuse despues, y dicen cual es cada una.
        if opciones.get('transcript'):
            # Lo que el hook habria visto si hubiera estado puesto: sale del
            # transcript de la sesion, que guarda cada llamada al tool Agent con
            # su gasto y su hora real (§22).
            resultado = exportar_transcript(
                ruta_config=opciones.get('config') or 'config.json', aviso=_aviso)
            if not resultado['enviado']:
                _log('no se mando nada: {}'.format(resultado['motivo']))
                return
            _log('{} de {} llamada(s) trazadas desde {}'.format(
                resultado['trazadas'], resultado['llamadas'], resultado['directorio']))
            _log('  con prompt, tokens, modelo y latencia reales')
            return

        modelo = opciones.get('modelo')
        resultado = exportar_trazas_cc(
            config, modelo=modelo if isinstance(modelo, str) else None, aviso=_aviso)
        resumen = resultado.get('plan') or {}
        if not resultado['enviado']:
            _log('no se mando nada: {}'.format(resultado['motivo']))
            return
        _log('{} traza(s) en la sesion {}'.format(resultado['trazas'], resultado['sesion']))
        _log('  {} intento(s), {} nota(s), {} retoque(s), entorno {}'.format(
            resumen.get('intentos'), resumen.get('notas'), resumen.get('retoques'),
            resumen.get('entorno')))
        _log('  reconstruido del canon: sin latencia, sin tokens y sin coste')

    elif comando == 'informe-trazas':
        sesion = opciones.get('sesion')
        informe, motivo = construir_informe(
            config, sesion=sesion if isinstance(sesion, str) else None, aviso=_aviso)
        if informe is None:
            _log('sin informe: {}'.format(motivo))
            return
        salida = texto_informe(informe, informe['sesion'])
        destino = opciones.get('salida')
        if opciones.get('json'):
            salida = json.dumps(informe, indent=2, ensure_ascii=False)
        if isinstance(destino, str):
            Path(destino).write_text(salida + '\n', encoding='utf-8')
            _log('informe escrito en {}'.format(destino))
        else:
            _log(salida)

    else:
        raise ValueError('comando desconocido: {}\n\n{}'.format(comando, AYUDA))


def main(argv=None):
    # Salida en LF tambien en Windows: lo que se imprime aqui se compara y se
    # canaliza, y no queremos que cambie segun el sistema.
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, 'reconfigure'):
            canal.reconfigure(newline='\n')

    posicionales, opciones = _parsear(sys.argv[1:] if argv is None else argv)
    comando = posicionales[0] if posicionales else None
    if not comando or comando == 'ayuda' or opciones.get('help'):
        _log(AYUDA)
        return 0

    if comando == 'hook-traza':
        # Corta aqui a proposito: este comando corre una vez por cada llamada a
        # un subagente y no necesita el perfil validado. Devuelve 0 siempre, que
        # es la regla de §22: un hook no puede parar una novela.
        cargar_entorno()
        return trazar_desde_stdin(ruta_config=opciones.get('config') or 'config.json')

    # El .env antes que nada: de ahi salen las credenciales de §20, y el SDK de
    # Langfuse las lee en el momento de construirse.
    cargar_entorno()

    try:
        config = cargar_config(opciones.get('config') or 'config.json')
        _ejecutar(comando, posicionales, opciones, config)
    except ErrorConfig as e:
        sys.stderr.write('\n{}\n\nSe para al arrancar: una errata en un umbral sale'
                         ' mas barata descubierta ahora que tres capitulos'
                         ' despues.\n'.format(e))
        return 1
    except Exception as e:
        sys.stderr.write('\nerror: {}\n'.format(e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
