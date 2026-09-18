# §21 La biblioteca: todas las novelas, una carpeta cada una.
#
# **Por que no hay una carpeta de trabajo.** La habia -`novela-cc/`- y era el
# origen de todo lo manual: como el orquestador escribia siempre en la misma
# ruta, empezar un libro encima del anterior lo pisaba, y para evitarlo habia que
# acordarse de copiar y de borrar antes de arrancar. Una novela que nace ya en su
# sitio definitivo no necesita que nadie la ponga a salvo despues.
#
# Aqui no se escribe canon: se crea la carpeta y se dice cual es. Dentro escribe
# el orquestador y nadie mas, que es la primera regla de §21 y no se toca.
import re
import unicodedata
from datetime import date
from pathlib import Path

RAIZ = 'biblioteca'

# Lo que cuelga de la carpeta de una novela. No se crea aqui -lo crea quien
# escribe- pero da igual el orden: esto solo necesita saber donde mirar.
CANON = 'canon'
BRIEF = 'canon/brief.json'
ESTADO = 'canon/estado.json'


class ErrorBiblioteca(Exception):
    """No se pudo crear o encontrar una novela."""


def _sin_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn')


def nombre_para(brief, hoy=None):
    """El nombre de carpeta de una novela: fecha y epoca.

    Sale del brief y no de un contador porque un `novela-3/` no dice nada seis
    meses despues, y la epoca es lo primero que uno recuerda de un libro. La
    fecha delante para que el listado salga ordenado solo.
    """
    epoca = str((brief or {}).get('epoca') or '').strip()
    # Solo hasta la primera coma: "Sevilla, 1587, barrio de Triana" es un nombre
    # de carpeta imposible, y "sevilla-1587" es justo lo que se recuerda.
    cabeza, _, resto = epoca.partition(',')
    ano = re.search(r'\b(1\d{3}|20\d{2})\b', resto or epoca)
    apodo = '-'.join(t for t in (cabeza, ano.group(1) if ano else '') if t.strip())
    apodo = re.sub(r'[^a-z0-9]+', '-', _sin_acentos(apodo).lower()).strip('-')
    return '{}-{}'.format(hoy or date.today().isoformat(), apodo or 'novela')


def ruta_de(nombre, raiz=RAIZ):
    return Path(raiz) / nombre


def crear(brief, raiz=RAIZ, hoy=None):
    """Aparta la carpeta de una novela nueva y devuelve donde ha quedado.

    **Crea el directorio y nada mas.** El brief, el dossier y todo lo demas los
    escribe el orquestador: la primera regla de §21 dice que en el canon escribe
    el y nadie mas, y un directorio vacio no es canon.

    Si el nombre ya esta cogido -dos novelas de la misma epoca el mismo dia- se
    numera, en vez de fallar o de escribir encima.
    """
    base = nombre_para(brief, hoy)
    nombre, intento = base, 2
    while ruta_de(nombre, raiz).exists():
        nombre = '{}-{}'.format(base, intento)
        intento += 1
        if intento > 99:
            raise ErrorBiblioteca('demasiadas novelas con el nombre {}'.format(base))

    destino = ruta_de(nombre, raiz)
    destino.mkdir(parents=True)
    return {'nombre': nombre, 'ruta': destino.as_posix()}


def _cuando(carpeta):
    """La ultima senal de vida de una novela.

    El estado se reescribe en cuanto algo cambia (§21), asi que su fecha es la
    del ultimo trabajo de verdad. Si aun no hay estado, vale la de la carpeta:
    una novela recien apartada tambien cuenta como la mas reciente.
    """
    for relativa in (ESTADO, BRIEF):
        fichero = carpeta / relativa
        if fichero.is_file():
            return fichero.stat().st_mtime
    return carpeta.stat().st_mtime


def carpetas(raiz=RAIZ):
    ruta = Path(raiz)
    if not ruta.is_dir():
        return []
    return [d for d in ruta.iterdir() if d.is_dir()]


def listar(raiz=RAIZ):
    """Las novelas, de la que se toco mas recientemente a la mas antigua."""
    salida = []
    for carpeta in sorted(carpetas(raiz), key=_cuando, reverse=True):
        salida.append({'nombre': carpeta.name,
                       'ruta': carpeta.as_posix(),
                       'cuando': _cuando(carpeta),
                       'empezada': (carpeta / BRIEF).is_file()})
    return salida


def actual(raiz=RAIZ, nombre=None):
    """La novela sobre la que se trabaja ahora, o None si no hay ninguna.

    Es la que se toco mas recientemente, y no un puntero guardado en un fichero:
    un puntero es un segundo sitio donde vive el estado, y se queda desfasado el
    dia que alguien mueve una carpeta a mano. La fecha del estado no miente.

    Con `nombre` se elige a dedo, que es lo que hace `--novela` en el CLI.
    """
    if nombre:
        carpeta = ruta_de(nombre, raiz)
        if not carpeta.is_dir():
            raise ErrorBiblioteca('no hay ninguna novela que se llame {} en {}/'.format(
                nombre, raiz))
        return carpeta.as_posix()
    novelas = listar(raiz)
    return novelas[0]['ruta'] if novelas else None
