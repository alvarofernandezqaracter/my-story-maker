# §12 Modo de ejecucion simulado. Capa local que resuelve las llamadas a
# agentes devolviendo respuestas fijas con el formato correcto. El resto del
# harness no sabe cual de los dos modos esta activo, asi que los tests y las
# demostraciones corren sin red y sin coste por el mismo camino que la
# ejecucion de verdad.
#
# Nada de lo que hay aqui es prosa que valga: es relleno con la forma exacta
# que los validadores de §9 y el gate de §8 esperan.
import math
import os
import re
import unicodedata

from .esquemas import DIMENSIONES


def slug(texto):
    descompuesto = unicodedata.normalize('NFD', str(texto))
    sin_tildes = ''.join(c for c in descompuesto if not '̀' <= c <= 'ͯ')
    limpio = re.sub(r'[^a-z0-9]+', '-', sin_tildes.lower())
    return re.sub(r'^-|-$', '', limpio)[:40]


def _anyo_de(epoca):
    m = re.search(r'\b(\d{3,4})\b', str(epoca))
    return int(m.group(1)) if m else 1600


def _fecha_de_capitulo(epoca, numero):
    base = _anyo_de(epoca)
    mes = ((numero - 1) % 12) + 1
    anyo = base + (numero - 1) // 12
    return '{}-{:02d}'.format(anyo, mes)


# ---- inyeccion de fallos, para poder demostrar el gate y VD-08 sin tocar codigo
# Formato: "capitulo:intento,capitulo:intento". Solo tiene efecto en simulado.
def _inyectado(variable, capitulo, intento):
    bruto = os.environ.get(variable)
    if not bruto:
        return False
    return '{}:{}'.format(capitulo, intento) in [p.strip() for p in bruto.split(',')]


# --------------------------------------------------------------- investigador

CATEGORIAS = ['vestimenta', 'politica', 'comida', 'lenguaje']

PLANTILLA_DATO = {
    'vestimenta': 'Se lleva %s de pano basto, sin tintes caros, y el calzado se remienda antes que cambiarse.',
    'politica': 'Las ordenanzas locales las aplica %s, que cobra por licencia y no por justicia.',
    'comida': 'Se come %s a media manana y la carne aparece solo en dias senalados.',
    'lenguaje': 'Se trata de vuesa merced a quien tiene cargo y se tutea al aprendiz; %s es insulto serio.',
}

RELLENO = {
    'vestimenta': ['sayo pardo', 'jubon remendado', 'capa corta'],
    'politica': ['el veinticuatro del cabildo', 'el alguacil mayor', 'el juez de la aduana'],
    'comida': ['pan de centeno con aceite', 'sopa de ajo', 'sardina en salazon'],
    'lenguaje': ['llamar a alguien converso', 'mentar el oficio del padre', 'nombrar la carcel'],
}


def investigador(entrada):
    brief = entrada['brief']
    datos = []
    for categoria in CATEGORIAS:
        for i in range(1, 4):
            # Por indice y no por hash: tres datos por categoria, tres rellenos
            # distintos, sin duplicados en el dossier.
            relleno = RELLENO[categoria][(i - 1) % len(RELLENO[categoria])]
            # Sin busqueda web (§12, F6) el investigador no puede marcar verificado
            # nada que solo recuerde: alterna sin_verificar e inventado.
            estado = 'inventado' if i == 3 else 'sin_verificar'
            datos.append({
                'id': 'dato-{}-{}'.format(categoria, i),
                'categoria': categoria,
                'dato': PLANTILLA_DATO[categoria].replace('%s', relleno, 1),
                'fuente': 'modelo',
                'estado': estado,
                'etiquetas': [categoria,
                              slug(brief['epoca']).split('-')[0] or 'epoca',
                              '{}-{}'.format(categoria, i)],
            })
    return {'datos': datos}


# ------------------------------------------------------------------ arquitecto

REPARTO = [
    {'nombre': 'Ines de Arteaga', 'rol': 'protagonista',
     'voz': 'Frases cortas y secas. Usa terminos de oficio con naturalidad. Nunca jura en voz alta.',
     'motivacion': 'Recuperar el nombre de su padre, condenado sin juicio.',
     'arco': 'De obedecer las reglas del gremio a romperlas a sabiendas.',
     'ubicacion': 'en la casa familiar'},
    {'nombre': 'Martin Coloma', 'rol': 'secundario',
     'voz': 'Habla de mas cuando esta nervioso y se corrige a media frase.',
     'motivacion': 'Conservar el puesto que le costo diez anos conseguir.',
     'arco': 'De comodo a comprometido, tarde y a su pesar.',
     'ubicacion': 'en la oficina del cabildo'},
    {'nombre': 'Dona Ursula Pardo', 'rol': 'secundario',
     'voz': 'Cortesia impecable usada como arma. Nunca levanta la voz.',
     'motivacion': 'Que el asunto se cierre antes de que llegue a oidos de la corte.',
     'arco': 'De arbitro neutral a parte interesada.',
     'ubicacion': 'en su casa de la plaza'},
    {'nombre': 'El escribano Lucas', 'rol': 'figurante',
     'voz': 'Habla en formulas de registro incluso fuera del oficio.',
     'motivacion': 'Cobrar sus derechos sin meterse en nada.',
     'arco': 'Sigue igual al final que al principio, y eso importa.',
     'ubicacion': 'en la escribania'},
]


def arquitecto(entrada):
    brief = entrada['brief']
    dossier = entrada.get('dossier') or []

    personajes = [{**p, 'id': slug(p['nombre']), 'sabe': []} for p in REPARTO]

    etiquetas_disponibles = list(dict.fromkeys(
        etiqueta for d in dossier for etiqueta in d['etiquetas']))

    total = brief['capitulos']
    capitulos = []

    for n in range(1, total + 1):
        if n <= math.ceil(total * 0.25):
            acto = 1
        elif n <= math.ceil(total * 0.75):
            acto = 2
        else:
            acto = 3

        reparto = [p['id'] for i, p in enumerate(personajes)
                   if i == 0 or (n + i) % 3 != 0]

        if etiquetas_disponibles:
            etiquetas = [CATEGORIAS[(n - 1) % len(CATEGORIAS)],
                         etiquetas_disponibles[(n * 2) % len(etiquetas_disponibles)]]
        else:
            etiquetas = [CATEGORIAS[(n - 1) % len(CATEGORIAS)]]

        capitulos.append({
            'numero': n,
            'titulo': 'Capitulo {}'.format(n),
            'acto': acto,
            'sinopsis': (
                'Inés de Arteaga da un paso mas en el asunto que abre la novela.'
                ' El acto {} exige que algo se cierre y algo quede abierto,'
                ' y aqui le toca a la pieza {} de {}.'.format(acto, n, total)),
            'fecha': _fecha_de_capitulo(brief['epoca'], n),
            'personajes': list(dict.fromkeys(reparto)),
            'etiquetas': list(dict.fromkeys(etiquetas)),
            'objetivo': (
                'Al acabar el capitulo {}, la protagonista sabe una cosa que al empezar'
                ' ignoraba y ha perdido una opcion que tenia.'.format(n)),
            'palabras_objetivo': brief['palabras_por_capitulo'],
        })

    return {'personajes': personajes, 'capitulos': capitulos}


# -------------------------------------------------------------------- escritor

PARRAFOS = [
    'La manana entro por el postigo con el olor de siempre, a cuerda mojada y a ceniza fria. %NOMBRE% no se movio de la silla hasta que el ruido de la calle tuvo la forma que esperaba.',
    'Habia aprendido a contar los pasos ajenos. Dos cortos y uno largo era el aguacil; tres iguales, cualquiera con prisa y sin cargo. Los de aquella manana no eran ninguno de los dos.',
    'Lo que dijeron despues no le sorprendio tanto como la manera de decirlo, con las manos quietas y la mirada en el suelo, como quien repite algo aprendido la noche anterior.',
    'Salio sin cerrar del todo. En la esquina el mercado ya estaba montado y el precio del pan seguia clavado donde el cabildo lo habia dejado, que era lo unico que en aquel ano no se movia.',
    'Penso en su padre y aparto el pensamiento con el mismo gesto con que se aparta una mosca: sin rabia, porque la rabia cansa, y ella necesitaba el dia entero.',
    'El papel estaba doblado en cuatro y tenia una mancha en el borde. No hizo falta leerlo dos veces; hizo falta decidir si convenia haberlo leido, que es otra cosa.',
    'Al volver, la casa estaba como la habia dejado salvo en un detalle, y el detalle era el que importaba. Se quedo un rato largo mirandolo antes de tocar nada.',
    'Por la noche escribio dos lineas y quemo la primera. La segunda la dejo encima de la mesa, donde cualquiera que entrase iba a verla, que era exactamente lo que buscaba.',
]


def escritor(entrada):
    ficha = entrada['encargo']
    personajes = entrada.get('personajes') or []
    incidencias = entrada.get('incidencias') or []
    texto_previo = entrada.get('texto_previo')
    nombre = personajes[0]['nombre'] if personajes else 'La protagonista'
    intento = entrada.get('intento') or 1

    # Gancho de simulacion: un capitulo deliberadamente corto para ejercitar VD-08.
    if _inyectado('NOVELA_SIM_CORTOS', ficha['numero'], intento):
        return {
            'texto': '# {}\n\nUn parrafo y nada mas, que es justo lo que VD-08 tiene que cazar.'
                     .format(ficha['titulo']),
            'faltantes': [],
        }

    objetivo = ficha['palabras_objetivo']
    cuerpo = []
    palabras = 0
    i = 0
    while palabras < objetivo - 12:
        base = PARRAFOS[i % len(PARRAFOS)].replace('%NOMBRE%', nombre, 1)
        parrafo = base if i < len(PARRAFOS) else '{} ({}, hilo {})'.format(
            base, ficha['titulo'], i)
        cuerpo.append(parrafo)
        palabras += len(re.findall(r'\S+', parrafo))
        i += 1

    cabecera = ['# {}'.format(ficha['titulo'])]
    if texto_previo and incidencias:
        # Arreglo quirurgico: el texto de salida sigue siendo el capitulo entero.
        cabecera.append('<!-- reescritura sobre {} incidencia(s) -->'.format(len(incidencias)))

    return {
        'texto': '\n\n'.join(cabecera + cuerpo),
        # §5: si le falta un detalle de epoca resuelve la escena sin el y lo anota.
        'faltantes': (['Falta un dato concreto de {} para el capitulo {}'.format(
            ficha['etiquetas'][0], ficha['numero'])] if ficha['etiquetas'] else []),
    }


# ------------------------------------------------------------------- validador

def validador(entrada):
    encargo = entrada['encargo']
    dimension = entrada.get('dimension')
    intento = entrada.get('intento') or 1
    numero = encargo['numero']
    malo = _inyectado('NOVELA_SIM_FALLOS', numero, intento)

    def bloque(dim):
        if malo:
            es_continuidad = dim == 'continuidad'
            return {
                'dimension': dim,
                'nota': 2 if es_continuidad else 3,
                'incidencias': [{
                    'cita': 'La casa estaba como la habia dejado',
                    'severidad': 'grave',
                    'sugerencia': 'El canon situa a la protagonista fuera de la casa desde el capitulo anterior.',
                }] if es_continuidad else [{
                    'cita': 'el precio del pan seguia clavado',
                    'severidad': 'aviso',
                    'sugerencia': 'Apoyalo en un dato del dossier o quitalo.',
                }],
            }
        return {
            'dimension': dim,
            'nota': 4,
            'incidencias': [{
                'cita': 'Por la noche escribio dos lineas',
                'severidad': 'aviso',
                'sugerencia': 'La escena final puede cerrar medio parrafo antes.',
            }] if dim == 'logica_ritmo' else [],
        }

    dims = [dimension] if dimension else DIMENSIONES
    return {'revisiones': [bloque(d) for d in dims]}


# -------------------------------------------------------------------- cronista

def cronista(entrada):
    ficha = entrada['ficha']
    personajes = entrada['personajes']
    presentes = [p['id'] for p in personajes]
    primero = personajes[0]['nombre'] if personajes else 'la protagonista'

    if ficha['numero'] > 1:
        hilos_cerrados = ['Hilo abierto en el capitulo {}: {}'.format(
            ficha['numero'] - 1,
            ficha['objetivo'].replace(
                'capitulo {}'.format(ficha['numero']),
                'capitulo {}'.format(ficha['numero'] - 1), 1))]
    else:
        hilos_cerrados = []

    return {
        'resumen': (
            'En el capitulo {}, {} Al cerrar, la posicion de {} ha cambiado y el asunto'
            ' principal avanza un escalon.'.format(
                ficha['numero'], ficha['sinopsis'], primero)),
        'hilos_abiertos': ['Hilo abierto en el capitulo {}: {}'.format(
            ficha['numero'], ficha['objetivo'])],
        'hilos_cerrados': hilos_cerrados,
        'personajes_presentes': presentes,
        'cambios_personaje': [{
            'id': p['id'],
            'ubicacion': '{} (cap. {})'.format(
                re.sub(r' \(cap\. \d+\)$', '', p['ubicacion']), ficha['numero']),
            'sabe': list(dict.fromkeys(
                list(p['sabe']) + ['Lo ocurrido en el capitulo {}'.format(ficha['numero'])])),
        } for p in personajes],
        'eventos': [{
            'id': 'evento-cap-{}'.format(ficha['numero']),
            'tipo': 'trama',
            'fecha': ficha['fecha'],
            'descripcion': 'Sucesos del capitulo {}: {}.'.format(
                ficha['numero'], ficha['titulo']),
            'capitulo': ficha['numero'],
            'personajes': presentes,
        }],
    }


# --------------------------------------------------------------- editor global

def editor_global(entrada):
    resumenes = entrada.get('resumenes') or []
    hilos_vivos = entrada.get('hilos_vivos') or []
    personajes = entrada.get('personajes') or []
    retoques = []

    for i, hilo in enumerate(hilos_vivos[:5]):
        retoques.append({
            'id': 'RET-{:02d}'.format(i + 1),
            'tipo': 'promesa',
            'capitulos': [hilo['capitulo']],
            'descripcion': 'Queda sin saldar: {}. Cierralo o retiralo del capitulo {}.'.format(
                hilo['hilo'], hilo['capitulo']),
            'severidad': 'grave' if i == 0 else 'aviso',
        })

    protagonista = next((p for p in personajes if p['rol'] == 'protagonista'), None)
    if protagonista:
        retoques.append({
            'id': 'RET-{:02d}'.format(len(retoques) + 1),
            'tipo': 'personaje',
            'capitulos': [1, len(resumenes)],
            'descripcion': (
                'El arco de {} se enuncia en el capitulo 1 y no vuelve a tocarse hasta el'
                ' final: falta un paso intermedio visible.'.format(protagonista['nombre'])),
            'severidad': 'aviso',
        })

    if len(resumenes) >= 3:
        retoques.append({
            'id': 'RET-{:02d}'.format(len(retoques) + 1),
            'tipo': 'ritmo',
            'capitulos': [r['capitulo'] for r in resumenes[1:-1]],
            'descripcion': ('El acto central avanza al mismo paso en todos los capitulos;'
                            ' conviene acelerar uno y frenar otro.'),
            'severidad': 'aviso',
        })

    return {'retoques': retoques}


AGENTES_SIMULADOS = {
    'investigador': investigador,
    'arquitecto': arquitecto,
    'escritor': escritor,
    'validador': validador,
    'cronista': cronista,
    'editor_global': editor_global,
}
