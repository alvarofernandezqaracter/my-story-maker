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

# Debajo de esto no se decide nada: un texto de dos frases no da senal.
MINIMO_PALABRAS = 40
# Cuantas veces tiene que ganar el otro idioma para llamarlo fallo. Amplio a
# proposito: el objetivo es cazar el capitulo entero en otro idioma, no la cita.
FACTOR = 1.5


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


def revisar(texto):
    """Devuelve (escalon, detalle). El escalon es 'ok', 'sin_datos' o 'bloqueo'."""
    c = contar(texto)
    if c['palabras'] < MINIMO_PALABRAS:
        return 'sin_datos', dict(c, motivo='texto demasiado corto para decidir')
    if c['ingles'] > c['espanol'] * FACTOR:
        return 'bloqueo', dict(
            c, motivo='parece escrito en ingles: %d funcionales inglesas frente '
                      'a %d espanolas' % (c['ingles'], c['espanol']))
    return 'ok', dict(c, motivo='')
