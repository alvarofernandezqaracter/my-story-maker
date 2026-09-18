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
from .biblioteca import actual, ErrorBiblioteca, listar as listar_novelas
from .entorno import cargar_entorno
from .informe import construir as construir_informe, texto as texto_informe
from .servidor import arrancar as arrancar_interfaz
from .trazas_cc import exportar as exportar_trazas_cc
from .trazas_hook import desde_stdin as trazar_desde_stdin

AYUDA = """
novela — utilidades del sistema de novelas historicas

La novela se escribe desde Claude Code: abre el repositorio y lanza
/orquestar-novela (§21). Lo de aqui es lo que mira ese trabajo por fuera.

  novela ui [--puerto N]           interfaz web en el navegador (§19). Mira la
                                   novela en curso y no escribe en ella
  novela trazar [--novela N] [--modelo M]
                                   manda a Langfuse el canon de una novela,
                                   reconstruido (§20). Sin --novela, la en curso
  novela biblioteca                lista las novelas, de la mas reciente a la
                                   mas antigua (§21)
  novela hook-traza                lee un PostToolUse por stdin y traza la
                                   llamada al subagente. Lo llama el hook (§22)
  novela informe-trazas [--sesion S] [--salida F] [--json]
                                   lee de vuelta las trazas de una novela y
                                   agrega el gasto para analizarlo (§22). Si
                                   Langfuse no contesta, tira del diario local
                                   del hook: sale todo menos el dinero

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
        # El hook de §22 traza cada llamada en vivo y trae el gasto. Esto trae
        # lo otro: las notas del gate, el veredicto y el escalon de VD-08, que
        # no son llamadas a ningun subagente y solo estan en el canon.
        modelo = opciones.get('modelo')
        cual = opciones.get('novela')
        resultado = exportar_trazas_cc(
            config, raiz=actual(nombre=cual) if isinstance(cual, str) else None,
            modelo=modelo if isinstance(modelo, str) else None, aviso=_aviso)
        resumen = resultado.get('plan') or {}
        if not resultado['enviado']:
            _log('no se mando nada: {}'.format(resultado['motivo']))
            return
        _log('{} traza(s) en la sesion {}'.format(resultado['trazas'], resultado['sesion']))
        _log('  {} intento(s), {} nota(s), {} retoque(s), entorno {}'.format(
            resumen.get('intentos'), resumen.get('notas'), resumen.get('retoques'),
            resumen.get('entorno')))
        _log('  reconstruido del canon: sin latencia, sin tokens y sin coste')

    elif comando == 'biblioteca':
        novelas = listar_novelas()
        if not novelas:
            _log('la biblioteca esta vacia. Se escribe una novela desde la pagina'
                 ' de §19 o lanzando /orquestar-novela en Claude Code.')
            return
        from .canon_cc import CanonCC
        for i, novela in enumerate(novelas):
            canon = CanonCC(novela['ruta'])
            escaleta = canon.escaleta()
            aprobados = sum(1 for c in escaleta if canon.intento_aprobado(c['numero']))
            _log('{} {}'.format('*' if i == 0 else ' ', novela['nombre']))
            if not novela['empezada']:
                _log('    apartada, sin brief todavia')
                continue
            _log('    {} | {} de {} capitulos aprobados'.format(
                canon.estado() or 'sin estado', aprobados, len(escaleta)))
            _log('    {}'.format((canon.brief() or {}).get('epoca') or ''))
        _log('')
        _log('El * es la novela en curso: la que se toco ultima.')

    elif comando == 'informe-trazas':
        sesion = opciones.get('sesion')
        informe, motivo = construir_informe(
            config, sesion=sesion if isinstance(sesion, str) else None, aviso=_aviso)
        if informe is None:
            _log('sin informe: {}'.format(motivo))
            return
        if informe.get('procedencia') == 'diario':
            _log('Langfuse no sirvio la sesion: {}'.format(informe['sin_langfuse']))
            _log('  informe hecho con el diario local: sin coste, el resto igual')
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
    except ErrorBiblioteca as e:
        sys.stderr.write('\n{}\n'.format(e))
        return 1
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
