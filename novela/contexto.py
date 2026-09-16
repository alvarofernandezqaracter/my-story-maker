# §7 Generador de contexto. Codigo, no agente: mismo capitulo y mismo canon dan
# siempre el mismo paquete. El escritor nunca consulta el canon por su cuenta.
import math
import re
from pathlib import Path

from .canon import normalizar_fecha

# Los cuatro bloques recortables, en el orden en que se recortan (§7).
ORDEN_DE_RECORTE = ['memoria_larga', 'cronologia', 'reparto_fondo', 'epoca']


def estimar_tokens(texto):
    """Estimacion de tokens suficiente para decidir recortes."""
    return math.ceil(len(str(texto)) / 4)


def _primera_frase(texto):
    corte = re.match(r'^.*?[.!?](\s|$)', str(texto), re.DOTALL)
    return (corte.group(0) if corte else str(texto)).strip()


def _ultimas_palabras(texto, cuantas):
    palabras = re.findall(r'\S+', str(texto).strip())
    return ' '.join(palabras[-cuantas:] if cuantas else palabras)


def _leer_texto(ruta):
    camino = Path(ruta)
    return camino.read_text(encoding='utf-8') if camino.exists() else ''


def _bloques(canon, numero, config):
    """Construye los nueve bloques de §7 para un capitulo.

    Devuelve el paquete sin recortar; el recorte lo aplica generar_contexto.
    """
    ficha = canon.ficha(numero)
    if not ficha:
        raise ValueError('no hay ficha del capitulo {}'.format(numero))

    todos_los_personajes = canon.personajes()
    en_escena = set(ficha['personajes'])

    # Encargo: la ficha entera, siempre.
    encargo = ficha

    # Personajes: fichas completas de quien sale.
    personajes = canon.personajes(ficha['personajes'])

    # Reparto de fondo: quien no sale pero se menciona en la sinopsis.
    sinopsis = ficha['sinopsis'].lower()
    reparto_fondo = [
        {'id': p['id'], 'nombre': p['nombre'], 'linea': _primera_frase(p['motivacion'])}
        for p in todos_los_personajes
        if p['id'] not in en_escena and p['nombre'].lower() in sinopsis
    ]

    # Memoria: resumenes de los capitulos aprobados anteriores.
    anteriores = [r for r in canon.resumenes() if r['capitulo'] < numero]
    corte = numero - config['contexto']['ventana_resumenes']
    memoria_reciente = [r for r in anteriores if r['capitulo'] >= corte]
    memoria_larga = [
        {'capitulo': r['capitulo'], 'resumen': _primera_frase(r['resumen'])}
        for r in anteriores if r['capitulo'] < corte
    ]

    # Hilos vivos: abiertos y aun no cerrados.
    hilos_vivos = canon.hilos_vivos()

    # Epoca: datos que casan con las etiquetas de la ficha, verificado primero.
    etiquetas = {str(e).lower() for e in ficha['etiquetas']}
    peso = {'verificado': 0, 'sin_verificar': 1, 'inventado': 2}
    epoca = sorted(
        (d for d in canon.datos()
         if any(str(e).lower() in etiquetas for e in d['etiquetas'])),
        key=lambda d: (peso.get(d['estado'], 9), d['id']),
    )

    # Cronologia: eventos entre la fecha de la ficha anterior y la de esta.
    previas = [f for f in canon.fichas() if f['numero'] < numero]
    ficha_anterior = previas[-1] if previas else None
    desde = normalizar_fecha(ficha_anterior['fecha']) if ficha_anterior else None
    hasta = normalizar_fecha(ficha['fecha'])

    cronologia = []
    for e in canon.eventos():
        f = normalizar_fecha(e['fecha'])
        if not f or not hasta:
            continue
        if (desde is None or f >= desde) and f <= hasta:
            cronologia.append(e)

    # Enganche: cola literal del capitulo anterior aprobado.
    enganche = ''
    if ficha_anterior:
        aprobado = canon.intento_aprobado(ficha_anterior['numero'])
        if aprobado:
            enganche = _ultimas_palabras(
                _leer_texto(aprobado['ruta']), config['contexto']['palabras_enganche'])

    return {
        'encargo': encargo,
        'personajes': personajes,
        'reparto_fondo': reparto_fondo,
        'memoria_reciente': memoria_reciente,
        'memoria_larga': memoria_larga,
        'hilos_vivos': hilos_vivos,
        'epoca': epoca,
        'cronologia': cronologia,
        'enganche': enganche,
    }


def serializar(paquete):
    """Serializa el paquete en el orden de §7.

    Este es el formato que el escritor espera; la skill formato-paquete-contexto
    describe el mismo contrato en prosa.
    """
    b = paquete['bloques']
    partes = []

    partes.append('# Encargo del capitulo {}'.format(b['encargo']['numero']))
    partes.append('\n'.join([
        '- Titulo: {}'.format(b['encargo']['titulo']),
        '- Acto: {}'.format(b['encargo']['acto']),
        '- Fecha: {}'.format(b['encargo']['fecha']),
        '- Objetivo: {}'.format(b['encargo']['objetivo']),
        '- Palabras objetivo: {}'.format(b['encargo']['palabras_objetivo']),
        '- Sinopsis: {}'.format(b['encargo']['sinopsis']),
    ]))

    partes.append('# Personajes en escena')
    fichas_personaje = '\n\n'.join('\n'.join([
        '## {} ({}, {})'.format(p['nombre'], p['id'], p['rol']),
        '- Voz: {}'.format(p['voz']),
        '- Motivacion: {}'.format(p['motivacion']),
        '- Arco: {}'.format(p['arco']),
        '- Donde esta: {}'.format(p['ubicacion']),
        '- Que sabe: {}'.format(' | '.join(p['sabe']) if p['sabe'] else '(sin anotar)'),
    ]) for p in b['personajes'])
    partes.append(fichas_personaje or '(ninguno)')

    if b['reparto_fondo']:
        partes.append('# Reparto de fondo')
        partes.append('\n'.join('- {} ({}): {}'.format(p['nombre'], p['id'], p['linea'])
                                for p in b['reparto_fondo']))

    if b['memoria_reciente']:
        partes.append('# Memoria reciente')
        partes.append('\n\n'.join('## Capitulo {}\n{}'.format(r['capitulo'], r['resumen'])
                                  for r in b['memoria_reciente']))

    if b['memoria_larga']:
        partes.append('# Memoria larga')
        partes.append('\n'.join('- Cap. {}: {}'.format(r['capitulo'], r['resumen'])
                                for r in b['memoria_larga']))

    if b['hilos_vivos']:
        partes.append('# Hilos vivos')
        partes.append('\n'.join('- (abierto en cap. {}) {}'.format(h['capitulo'], h['hilo'])
                                for h in b['hilos_vivos']))

    if b['epoca']:
        # En el paquete viaja el estado de cada dato: el escritor necesita saber
        # que es firme y que es relleno.
        partes.append('# Epoca')
        partes.append('\n'.join('- [{}] ({}) {} — fuente: {}'.format(
            d['estado'], d['categoria'], d['dato'], d['fuente']) for d in b['epoca']))

    if b['cronologia']:
        partes.append('# Cronologia')
        partes.append('\n'.join('- {} ({}) {}'.format(e['fecha'], e['tipo'], e['descripcion'])
                                for e in b['cronologia']))

    if b['enganche']:
        partes.append('# Enganche con el capitulo anterior')
        partes.append('> {}'.format(b['enganche']))

    return '\n\n'.join(partes)


def generar_contexto(canon, numero, config):
    """§7: si el paquete se pasa del tope se recorta en orden fijo.

    El encargo, los personajes y los hilos vivos no se recortan; si aun asi no
    cabe, el capitulo se marca bloqueado en lugar de escribirse con el contexto
    mutilado.
    """
    paquete = {'capitulo': numero, 'bloques': _bloques(canon, numero, config), 'recortes': []}
    tope = config['contexto']['tope_contexto']

    for nombre in ORDEN_DE_RECORTE:
        while (estimar_tokens(serializar(paquete)) > tope
               and len(paquete['bloques'][nombre]) > 0):
            paquete['bloques'][nombre] = paquete['bloques'][nombre][:-1]
            paquete['recortes'].append(nombre)
        if estimar_tokens(serializar(paquete)) <= tope:
            break

    paquete['texto'] = serializar(paquete)
    paquete['tokens'] = estimar_tokens(paquete['texto'])
    paquete['cabe'] = paquete['tokens'] <= tope
    paquete['recortes'] = list(dict.fromkeys(paquete['recortes']))
    return paquete
