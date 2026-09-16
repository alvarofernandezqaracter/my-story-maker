# CLI del harness. Ningun comando toma decisiones: solo carga config, abre el
# canon y llama al flujo. El estado vive en el canon, nunca aqui (§6, §13).
import json
import sys
from pathlib import Path

from .agentes import Agentes, ParadaDelProceso
from .canon import Canon
from .config import cargar_config, ErrorConfig
from .contexto import generar_contexto
from .entorno import cargar_entorno
from .flujo import preparar, escribir_capitulo, cerrar, reanudar, siguiente_capitulo
from .gate import media, notas
from .servidor import arrancar as arrancar_interfaz
from .skills import listar_skills
from .util import numero_corto

AYUDA = """
novela — sistema multiagente de novelas historicas

  novela init                      crea el canon vacio
  novela brief <fichero.json>      guarda el brief (§3) y deja el proyecto en borrador
  novela preparar                  investigador y arquitecto (§4, tramo de preparacion)
  novela escribir [--capitulo N]   loop de capitulo: escritor, validador, gate, cronista
  novela cerrar                    editor global y retoques.md (§11)
  novela reanudar                  sigue desde donde se quedo, sin argumentos (§13)
  novela estado                    estado del proyecto y de cada capitulo
  novela ver <que> [id]            dossier | personajes | escaleta | resumenes | timeline
                                   | contexto N | capitulo N
  novela poner <que> <fichero>     personaje | capitulo — escritura a mano en el canon
  novela desbloquear --capitulo N [--aprobar-intento K | --reiniciar]
  novela skills                    lista las skills que el harness carga
  novela ui [--puerto N]           interfaz web del brief en el navegador (§19)

Opciones globales: --config <ruta> (por defecto config.json)
                   --canon <ruta>  (por defecto canon.db)
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


def _volcar(valor):
    _log(json.dumps(valor, indent=2, ensure_ascii=False))


def _contar_diario(diario):
    for e in diario:
        tipo = e['tipo']
        if tipo == 'dossier':
            _log('  dossier: {} datos'.format(e['datos']))
        elif tipo == 'escaleta':
            _log('  escaleta: {} capitulos, {} personajes'.format(
                e['capitulos'], e['personajes']))
        elif tipo == 'recorte':
            _log('  cap. {}: contexto recortado ({})'.format(
                e['capitulo'], ', '.join(e['bloques'])))
        elif tipo == 'vd08':
            _log('  cap. {} intento {}: VD-08 — {}'.format(
                e['capitulo'], e['intento'], '; '.join(e['detalles'])))
        elif tipo == 'gate':
            desenlace = 'aprobado' if e['aprueba'] else 'rechazado ({})'.format(
                '; '.join(e['motivos']))
            _log('  cap. {} intento {}: notas {} media {} -> {}'.format(
                e['capitulo'], e['intento'],
                '/'.join(str(n) for n in e['notas']), numero_corto(e['media']), desenlace))
        elif tipo == 'canon':
            _log('  cap. {}: canon actualizado (+{} hilos, -{}, {} eventos)'.format(
                e['capitulo'], e['hilos_abiertos'], e['hilos_cerrados'], e['eventos']))
        elif tipo == 'bloqueado':
            _log('  cap. {} BLOQUEADO: {}'.format(e['capitulo'], e['motivo']))
        elif tipo == 'parada':
            _log('  parada: {}'.format(e['motivo']))
        elif tipo == 'trazas':
            _log('  trazas: {}'.format(e['motivo']))
        elif tipo == 'retoques':
            _log('  {} retoques en {}'.format(e['total'], e['ruta']))


def _leer_json(ruta):
    if not ruta or not Path(str(ruta)).exists():
        raise ValueError('no existe el fichero: {}'.format(ruta))
    return json.loads(Path(str(ruta)).read_text(encoding='utf-8'))


def _entero(valor, mensaje):
    try:
        return int(str(valor))
    except (TypeError, ValueError):
        raise ValueError(mensaje) from None


def _ejecutar(comando, posicionales, opciones, canon, agentes, config, ruta_canon):
    # ---------------------------------------------------------------- F0
    if comando == 'init':
        _log('canon listo en {}'.format(ruta_canon))
        _log('modo de ejecucion: {}'.format(config['ejecucion']['modo']))

    elif comando == 'brief':
        brief = _leer_json(posicionales[1] if len(posicionales) > 1 else None)
        for campo in ('epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo'):
            if brief.get(campo) is None:
                raise ValueError('al brief le falta "{}"'.format(campo))
        p = canon.guardar_brief(brief)
        _log('brief guardado: {} capitulos de {} palabras'.format(
            p['capitulos'], p['palabras_por_capitulo']))
        _log('estado: {}'.format(p['estado']))

    elif comando == 'poner':
        que = posicionales[1] if len(posicionales) > 1 else None
        datos = _leer_json(posicionales[2] if len(posicionales) > 2 else None)
        lista = datos if isinstance(datos, list) else [datos]
        if que == 'personaje':
            canon.guardar_personajes(lista)
            _log('{} personaje(s)'.format(len(lista)))
        elif que == 'capitulo':
            canon.guardar_fichas(lista)
            _log('{} ficha(s)'.format(len(lista)))
        elif que == 'dato':
            canon.guardar_datos(lista)
            _log('{} dato(s)'.format(len(lista)))
        else:
            raise ValueError('poner acepta: personaje | capitulo | dato')

    elif comando == 'ver':
        que = posicionales[1] if len(posicionales) > 1 else None
        arg = posicionales[2] if len(posicionales) > 2 else None
        if que == 'dossier':
            _volcar(canon.datos())
        elif que == 'personajes':
            _volcar(canon.personajes())
        elif que == 'escaleta':
            _volcar(canon.fichas())
        elif que == 'resumenes':
            _volcar(canon.resumenes())
        elif que == 'timeline':
            _volcar(canon.eventos())
        elif que == 'hilos':
            _volcar(canon.hilos_vivos())
        elif que == 'contexto':
            p = generar_contexto(canon, _entero(arg, 'ver contexto necesita un numero'), config)
            recorte = ' (recortado: {})'.format(', '.join(p['recortes'])) if p['recortes'] else ''
            _log('# paquete de contexto — {} tokens estimados{}\n'.format(p['tokens'], recorte))
            _log(p['texto'])
        elif que == 'capitulo':
            n = _entero(arg, 'ver capitulo necesita un numero')
            _volcar({'ficha': canon.ficha(n), 'intentos': canon.intentos(n)})
        else:
            raise ValueError('ver acepta: dossier | personajes | escaleta | resumenes'
                             ' | timeline | hilos | contexto N | capitulo N')

    elif comando == 'estado':
        p = canon.proyecto()
        if not p:
            _log('no hay brief todavia')
            return
        _log('proyecto: {}   ({})'.format(p['estado'], p['epoca']))
        _log('modo: {}   validador: {}'.format(
            config['ejecucion']['modo'], config['validador']['modo']))
        fichas = canon.fichas()
        if not fichas:
            _log('sin escaleta')
            return
        for f in fichas:
            intentos = canon.intentos(f['numero'])
            aprobado = next((i for i in intentos if i['estado'] == 'aprobado'), None)
            if aprobado and aprobado['revisiones']:
                ns = notas(aprobado['revisiones'])
                nota = ' notas {} media {:.2f}'.format(
                    '/'.join(str(n) for n in ns), media(ns))
            else:
                nota = ''
            _log('  {:>3}  {:<10} {} intento(s){}  {}'.format(
                f['numero'], f['estado'], len(intentos), nota, f['titulo']))

    # ------------------------------------------------------- F1 a F5
    elif comando == 'preparar':
        resultado = preparar(canon, agentes, config)
        _contar_diario(resultado['diario'])
        _log('estado: {}'.format(resultado['estado']))

    elif comando == 'escribir':
        diario = []
        if opciones.get('capitulo'):
            r = escribir_capitulo(
                canon, agentes, config,
                _entero(opciones['capitulo'], 'escribir --capitulo necesita un numero'),
                diario)
            _contar_diario(diario)
            _log('capitulo aprobado' if r['aprobado']
                 else 'capitulo no aprobado: {}'.format(r['motivo']))
            return

        siguiente = siguiente_capitulo(canon)
        if not siguiente:
            _log('no quedan capitulos por escribir')
            return
        while siguiente:
            r = escribir_capitulo(canon, agentes, config, siguiente['numero'], diario)
            if not r['aprobado']:
                break
            siguiente = siguiente_capitulo(canon)
        _contar_diario(diario)
        if not siguiente_capitulo(canon):
            canon.marcar_estado('escrito')
            _log('todos los capitulos aprobados: el proyecto pasa a escrito')

    elif comando == 'cerrar':
        if canon.estado() != 'escrito':
            raise ValueError('el editor global corre con el proyecto en escrito, y esta en'
                             ' {}'.format(canon.estado()))
        resultado = cerrar(canon, agentes)
        _contar_diario(resultado['diario'])
        _log('{} retoques en {}'.format(len(resultado['retoques']), resultado['ruta']))

    elif comando == 'reanudar':
        r = reanudar(canon, agentes, config)
        _contar_diario(r['diario'])
        _log('estado: {}'.format(r['estado']))

    # ------------------------------------- salidas manuales del bloqueo (§8)
    elif comando == 'desbloquear':
        if not opciones.get('capitulo'):
            raise ValueError('desbloquear necesita --capitulo N')
        n = _entero(opciones['capitulo'], 'desbloquear necesita --capitulo N')
        if not canon.ficha(n):
            raise ValueError('no hay capitulo {}'.format(n))

        if opciones.get('aprobar-intento'):
            k = _entero(opciones['aprobar-intento'], '--aprobar-intento necesita un numero')
            if not any(i['intento'] == k for i in canon.intentos(n)):
                raise ValueError('el capitulo {} no tiene intento {}'.format(n, k))
            canon.fijar_intento_aprobado(n, k)
            canon.marcar_ficha(n, 'aprobado')
            _log('intento {} del capitulo {} aprobado a mano.'.format(k, n))
            _log('Ojo: el cronista no ha corrido, asi que el canon no tiene su resumen.')
            _log('Lanza "novela escribir --capitulo {}" si quieres regenerarlo entero.'.format(n))
        elif opciones.get('reiniciar'):
            for i in canon.intentos(n):
                canon.marcar_intento(n, i['intento'], 'descartado')
            canon.marcar_ficha(n, 'pendiente')
            _log('capitulo {} a cero: los intentos quedan como rastro en capitulos/'.format(n))
        else:
            canon.marcar_ficha(n, 'pendiente')
            _log('capitulo {} desbloqueado, el contador de intentos parte de cero'.format(n))
        canon.marcar_estado('escribiendo')
        _log('proyecto: escribiendo')

    elif comando == 'ui':
        # La interfaz solo escribe el brief; el flujo sigue corriendo en la CLI.
        arrancar_interfaz(
            config, ruta_canon,
            puerto=_entero(opciones['puerto'], 'ui --puerto necesita un numero')
            if opciones.get('puerto') else None,
            abrir=not opciones.get('sin-navegador'),
            log=_log)

    elif comando == 'skills':
        for s in listar_skills():
            _log('  {:<26} {}'.format(s['nombre'], s['meta'].get('description') or ''))

    else:
        raise ValueError('comando desconocido: {}\n\n{}'.format(comando, AYUDA))


def main(argv=None):
    # Salida en LF tambien en Windows: lo que imprime el harness se compara y se
    # canaliza, y no queremos que cambie segun el sistema.
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, 'reconfigure'):
            canal.reconfigure(newline='\n')

    posicionales, opciones = _parsear(sys.argv[1:] if argv is None else argv)
    comando = posicionales[0] if posicionales else None
    if not comando or comando == 'ayuda' or opciones.get('help'):
        _log(AYUDA)
        return 0

    # El .env antes que nada: de ahi salen las credenciales de §12 y de §20, y
    # el SDK de Langfuse las lee en el momento de construirse.
    cargar_entorno()

    try:
        config = cargar_config(opciones.get('config') or 'config.json')
        ruta_canon = opciones.get('canon') or 'canon.db'
        canon = Canon(ruta_canon)
        agentes = Agentes(config, aviso=lambda m: sys.stderr.write('trazas: {}\n'.format(m)))
        if config['trazas']['activas'] and not agentes.trazas.activa:
            # Las trazas no paran nada, pero callarse por que no salen deja a
            # quien las busca mirando un panel vacio sin saber por que.
            _log('trazas desactivadas: {}'.format(agentes.trazas.motivo))
        try:
            _ejecutar(comando, posicionales, opciones, canon, agentes, config, ruta_canon)
        finally:
            agentes.trazas.cerrar()
            canon.cerrar()
    except ErrorConfig as e:
        sys.stderr.write('\n{}\n\nEl harness para al arrancar: una errata en un umbral'
                         ' sale mas barata descubierta ahora que tres capitulos'
                         ' despues.\n'.format(e))
        return 1
    except ParadaDelProceso as e:
        sys.stderr.write('\nEl proceso para: {}\n'.format(e.mensaje))
        for d in e.detalles:
            sys.stderr.write('  - {}\n'.format(d))
        sys.stderr.write('\nEl estado queda escrito en el canon.'
                         ' Mira y relanza con "reanudar".\n')
        return 1
    except Exception as e:
        sys.stderr.write('\nerror: {}\n'.format(e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
