# §21 El archivo de novelas.
#
# El canon de `novela-cc/` es de **una** novela: el orquestador escribe siempre
# ahi, asi que empezar la siguiente encima de la anterior la pisa. Hasta ahora la
# unica forma de conservar una era acordarse de copiarla a mano antes de
# arrancar, y eso es una novela perdida esperando a ocurrir.
#
# Esto copia el canon entero a `novelas/<nombre>/` y **no borra nada**. Vaciar
# `novela-cc/` sigue siendo un gesto de quien opera la maquina: es irreversible,
# y una orden que archiva y borra a la vez acaba borrando el dia que el archivado
# falla a medias.
#
# Como todo lo que hay en este paquete, no escribe en el canon: lo lee y lo copia.
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

from .canon_cc import CanonCC, RAIZ

ARCHIVO = 'novelas'


class ErrorArchivo(Exception):
    """No se pudo archivar. Nada se ha tocado."""


def _sin_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')


def nombre_para(canon, hoy=None):
    """El nombre de carpeta de una novela: fecha y epoca.

    Sale del brief y no de un contador porque un `novela-3/` no dice nada seis
    meses despues, y la epoca es lo primero que uno recuerda de un libro. La
    fecha delante para que el listado salga ordenado solo.
    """
    epoca = ((canon.brief() or {}).get('epoca') or '').strip()
    # Solo hasta la primera coma: "Sevilla, 1587, barrio de Triana" es un titulo
    # de carpeta imposible, y "sevilla" con su ano es justo lo que se recuerda.
    cabeza, _, resto = epoca.partition(',')
    ano = re.search(r'\b(1\d{3}|20\d{2})\b', resto or epoca)
    trozos = [cabeza, ano.group(1) if ano else '']
    apodo = '-'.join(t for t in trozos if t.strip())
    apodo = re.sub(r'[^a-z0-9]+', '-', _sin_acentos(apodo).lower()).strip('-')
    return '{}-{}'.format(hoy or date.today().isoformat(), apodo or 'novela')


def _resumen(canon):
    escaleta = canon.escaleta()
    aprobados = [c for c in escaleta if canon.intento_aprobado(c['numero'])]
    palabras = sum((canon.intento_aprobado(c['numero']) or {}).get('palabras') or 0
                   for c in aprobados)
    return {'estado': canon.estado(),
            'capitulos': len(escaleta),
            'aprobados': len(aprobados),
            'palabras': palabras}


def plan(raiz=RAIZ, archivo=ARCHIVO, hoy=None):
    """Que se archivaria y con que nombre, sin copiar nada."""
    canon = CanonCC(raiz)
    if not canon.existe:
        return {'puede': False, 'motivo': 'no hay canon en {}/'.format(raiz)}
    nombre = nombre_para(canon, hoy)
    destino = Path(archivo) / nombre
    datos = {'puede': not destino.exists(), 'nombre': nombre,
             'destino': destino.as_posix(), 'origen': raiz}
    datos.update(_resumen(canon))
    if destino.exists():
        datos['motivo'] = 'ya existe {}'.format(destino.as_posix())
    return datos


def archivar(raiz=RAIZ, archivo=ARCHIVO, nombre=None, hoy=None):
    """Copia el canon entero a `novelas/<nombre>/`. No borra el original.

    Se niega si el destino ya existe: archivar dos veces la misma novela es casi
    siempre un despiste, y sobrescribir seria perder la copia buena.
    """
    canon = CanonCC(raiz)
    if not canon.existe:
        raise ErrorArchivo('no hay canon en {}/ que archivar'.format(raiz))

    nombre = nombre or nombre_para(canon, hoy)
    destino = Path(archivo) / nombre
    if destino.exists():
        raise ErrorArchivo(
            '{} ya existe. Dale otro nombre con --nombre, o mueve el de antes'.format(
                destino.as_posix()))

    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(raiz, destino)
    datos = {'nombre': nombre, 'destino': destino.as_posix(), 'origen': raiz}
    datos.update(_resumen(canon))
    return datos


def listar(archivo=ARCHIVO):
    """Las novelas ya archivadas, de la mas nueva a la mas vieja."""
    raiz = Path(archivo)
    if not raiz.is_dir():
        return []
    salida = []
    for carpeta in sorted((d for d in raiz.iterdir() if d.is_dir()), reverse=True):
        canon = CanonCC(carpeta.as_posix())
        fila = {'nombre': carpeta.name, 'ruta': carpeta.as_posix()}
        if canon.existe:
            fila.update(_resumen(canon))
            fila['epoca'] = (canon.brief() or {}).get('epoca')
        salida.append(fila)
    return salida
