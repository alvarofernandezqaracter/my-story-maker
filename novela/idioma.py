# VD-14 (SPEC.md §9): el capitulo esta escrito en el idioma de la novela.
#
# Corre junto a VD-08, antes de los validadores, y por la misma razon: un
# capitulo en otro idioma no merece gastar tres llamadas. Salio de una pasada
# real en la que el escritor devolvio un capitulo entero en ingles y las tres
# dimensiones lo puntuaron 4/4/4 sin mencionarlo: ninguna rubrica mira el
# idioma, asi que hacia falta una comprobacion mecanica.
#
# El metodo es el mas tonto que funciona, y es deliberado: contar palabras
# funcionales. Son las que ningun texto largo puede evitar y las que ningun
# nombre propio ni tecnicismo contamina, asi que un parrafo en castellano con
# vocabulario latino sigue dando castellano. Nada de dependencias ni de red,
# como el resto del paquete.
import re
import unicodedata

# Funcionales de cada idioma. No se busca vocabulario: se busca el andamiaje.
ESPANOL = frozenset("""
    de la que el en y a los se del las un por con no una su para es al lo como
    mas pero sus le ya o este si porque esta entre cuando muy sobre tambien me
    hasta hay donde quien desde todo nos durante todos uno les ni contra otros
    ese eso ante ellos e esto mi antes algunos unos yo otro otras tenia era
    habia sin ser dos fue han
""".split())

INGLES = frozenset("""
    the of and to in that was it for with as his her she he had on at by not
    but they this from have were are be been which their there would could
    when what all one out up about into then than them its who him
""".split())

# Los dos umbrales viven en `config.json` y no aqui, que es la regla de
# SPEC.md §12: un numero escrito en el codigo es un numero que hay que tocar
# codigo para cambiar. `margenes.idioma_palabras_min` es por debajo de cuantas
# palabras no se decide nada, porque un texto de dos frases no da senal, y
# `margenes.idioma_factor` es cuantas veces tiene que ganar el otro idioma para
# llamarlo fallo. El segundo es amplio a proposito: lo que se caza es el
# capitulo entero en otro idioma, no la cita.


def _normalizar(texto):
    """Minusculas y sin tildes: `mas` y `más` son la misma palabra funcional."""
    plano = unicodedata.normalize('NFD', texto.lower())
    return ''.join(c for c in plano if unicodedata.category(c) != 'Mn')


def contar(texto):
    palabras = re.findall(r"[a-z]+", _normalizar(texto))
    return {
        'palabras': len(palabras),
        'espanol': sum(1 for p in palabras if p in ESPANOL),
        'ingles': sum(1 for p in palabras if p in INGLES),
    }


def revisar(texto, config):
    """Devuelve (escalon, detalle). El escalon es 'ok', 'sin_datos' o 'bloqueo'.

    `config` es el `config.json` ya cargado: los dos umbrales salen de ahi.
    """
    margenes = config['margenes']
    c = contar(texto)
    if c['palabras'] < margenes['idioma_palabras_min']:
        return 'sin_datos', dict(c, motivo='texto demasiado corto para decidir')
    if c['ingles'] > c['espanol'] * margenes['idioma_factor']:
        return 'bloqueo', dict(
            c, motivo='parece escrito en ingles: %d funcionales inglesas frente '
                      'a %d espanolas' % (c['ingles'], c['espanol']))
    return 'ok', dict(c, motivo='')
