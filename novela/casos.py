# §4 de AUTOAPRENDIZAJE.md. El dataset del banco: de donde salen los casos.
#
# **Los casos viven en Langfuse**, en dos datasets por rol -taller y reserva- y
# no en un fichero del repositorio. La particion no es una convencion que haya
# que recordar: son dos almacenes distintos, asi que el optimizador no puede ver
# la reserva ni por descuido.
#
# De cada lectura queda un espejo local, que es una cache y no una fuente de
# verdad: sirve para correr una ronda sin red y para poder mirar los casos sin
# abrir el navegador. Cuando Langfuse contesta, manda Langfuse.
#
# Los casos se sacan de novelas ya escritas. Es deliberado: un caso inventado
# para la ocasion mide lo comodo, y lo que hay que medir es lo que el sistema
# produce de verdad.
import hashlib
import json
from pathlib import Path

from .biblioteca import listar as listar_novelas
from .canon_cc import CanonCC

ESPEJO = 'autoaprendizaje/casos'

PARTICIONES = ('taller', 'reserva')

# En produccion el orquestador le pasa al escritor dos rutas: de donde leer el
# paquete y donde dejar el capitulo (§5). En el banco no hay repositorio que
# abrir, asi que el paquete va pegado y la ruta de salida es relativa. Es la
# unica diferencia entre el encargo de una novela y el de una corrida, y esta
# escrita aqui para que se vea.
ENCARGO_ESCRITOR = """PAQUETE DE CONTEXTO. Va pegado entero aqui abajo: no hay
ningun fichero que abrir y no existe `biblioteca/`.

{paquete}

Escribe el capitulo en `capitulo.md`, en el directorio en el que estas, y
responde solo con esa ruta."""


def nombre_dataset(rol, particion):
    return 'banco-{}-{}'.format(rol, particion)


def _semilla(caso):
    return hashlib.sha1(str(caso.get('id') or '').encode('utf-8')).hexdigest()


def repartir(casos):
    """Parte los casos en taller y reserva, siempre igual.

    Se ordena por el hash del id y se corta por la mitad. Del hash sale que la
    particion no dependa del orden en que se encontraron los casos ni de la
    fecha; del corte por la mitad, que las dos mitades sean comparables aunque
    haya seis casos. Un caso nuevo puede mover a otro de lado, y es el precio de
    tener siempre mitad y mitad: lo que no puede pasar es que la particion baile
    entre dos corridas de la misma ronda.
    """
    ordenados = sorted(casos, key=_semilla)
    mitad = len(ordenados) // 2
    return {'taller': ordenados[mitad:], 'reserva': ordenados[:mitad]}


# --- de donde se sacan --------------------------------------------------------

def _caso(ident, entrada, origen, **extra):
    caso = {'id': ident, 'entrada': entrada, 'origen': origen}
    caso.update({k: v for k, v in extra.items() if v is not None})
    return caso


def _de_investigador(canon, nombre):
    brief = canon.brief()
    if not brief:
        return []
    return [_caso('{}-brief'.format(nombre),
                  json.dumps(brief, ensure_ascii=False, indent=2), nombre)]


def _de_escritor(canon, nombre, raiz):
    """Un caso por paquete de contexto guardado.

    El paquete es exactamente lo que vio el escritor cuando redacto ese
    capitulo (§7 de SPEC.md), asi que medir sobre el es medir sobre el trabajo
    real y no sobre un encargo de mentira.
    """
    brief = canon.brief() or {}
    objetivo = brief.get('palabras_por_capitulo')
    casos = []
    for fichero in sorted(Path(raiz, 'contexto').glob('cap-*.md')):
        texto = fichero.read_text(encoding='utf-8', errors='replace')
        casos.append(_caso('{}-{}'.format(nombre, fichero.stem),
                           ENCARGO_ESCRITOR.format(paquete=texto), nombre,
                           palabras_objetivo=objetivo))
    return casos


def _de_validador(canon, nombre, raiz):
    """Un caso por intento redactado: el capitulo con su paquete delante."""
    casos = []
    for fichero in sorted(Path(raiz, 'capitulos').glob('cap-*-intento-*.md')):
        numero = fichero.stem.split('-')[1]
        paquete = Path(raiz, 'contexto', 'cap-{}.md'.format(numero))
        if not paquete.is_file():
            continue
        entrada = 'PAQUETE DE CONTEXTO\n\n{}\n\nCAPITULO REDACTADO\n\n{}'.format(
            paquete.read_text(encoding='utf-8', errors='replace'),
            fichero.read_text(encoding='utf-8', errors='replace'))
        casos.append(_caso('{}-{}'.format(nombre, fichero.stem), entrada, nombre))
    return casos


EXTRACTORES = {
    'investigador': lambda canon, nombre, raiz: _de_investigador(canon, nombre),
    'escritor': _de_escritor,
    'validador': _de_validador,
}


def de_la_biblioteca(rol):
    """Todos los casos de ese rol que dan las novelas ya escritas."""
    extractor = EXTRACTORES.get(rol)
    if extractor is None:
        return []
    casos = []
    for novela in listar_novelas():
        canon = CanonCC(novela['ruta'])
        if not canon.existe:
            continue
        casos.extend(extractor(canon, novela['nombre'], novela['ruta']))
    return casos


def reunir(objetivo):
    """Los casos de un objetivo: los de la biblioteca mas sus semillas.

    Las semillas van escritas en el propio objetivo y existen por un motivo
    concreto: hay roles de los que una biblioteca corta no da casos suficientes
    -del investigador sale un caso por novela, y nada mas-. Se marcan como tales
    para que se vea cuantos numeros vienen de trabajo real y cuantos no.
    """
    casos = de_la_biblioteca(objetivo['rol'])
    for i, semilla in enumerate(objetivo.get('semillas') or [], start=1):
        entrada = semilla.get('entrada')
        if isinstance(entrada, (dict, list)):
            entrada = json.dumps(entrada, ensure_ascii=False, indent=2)
        casos.append(_caso(semilla.get('id') or 'semilla-{:02d}'.format(i),
                           entrada, 'semilla',
                           palabras_objetivo=semilla.get('palabras_objetivo')))
    vistos, unicos = set(), []
    for caso in casos:
        if caso['id'] in vistos:
            continue
        vistos.add(caso['id'])
        unicos.append(caso)
    return unicos


# --- donde se guardan ---------------------------------------------------------

def _ruta_espejo(rol, particion, raiz=ESPEJO):
    return Path(raiz) / '{}.jsonl'.format(nombre_dataset(rol, particion))


def escribir_espejo(rol, particion, casos, raiz=ESPEJO):
    ruta = _ruta_espejo(rol, particion, raiz)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open('w', encoding='utf-8') as f:
        for caso in casos:
            f.write(json.dumps(caso, ensure_ascii=False) + '\n')
    return ruta


def leer_espejo(rol, particion, raiz=ESPEJO):
    ruta = _ruta_espejo(rol, particion, raiz)
    if not ruta.is_file():
        return []
    casos = []
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        if linea.strip():
            try:
                casos.append(json.loads(linea))
            except ValueError:
                continue
    return casos


def _cliente(trazas):
    """El cliente de Langfuse, o None. Nunca lanza.

    Misma regla que §20: ningun fallo de observabilidad para al banco. Sin
    Langfuse se corre con el espejo y se dice de donde salieron los casos.
    """
    try:
        return trazas.cliente if trazas is not None and trazas.activa else None
    except Exception:
        return None


def sembrar(objetivo, trazas=None, raiz=ESPEJO, aviso=None):
    """Reune los casos, los reparte y los sube. Devuelve el recuento.

    Subir dos veces el mismo caso no lo duplica: el id del item es el del caso,
    y Langfuse trata eso como la misma fila.
    """
    rol = objetivo['rol']
    partes = repartir(reunir(objetivo))
    cliente = _cliente(trazas)
    subidos = {}
    for particion in PARTICIONES:
        casos = partes[particion]
        escribir_espejo(rol, particion, casos, raiz)
        subidos[particion] = 0
        if cliente is None:
            continue
        nombre = nombre_dataset(rol, particion)
        try:
            cliente.create_dataset(
                name=nombre,
                description='Casos del banco para el rol {} ({})'.format(rol, particion),
                metadata={'rol': rol, 'particion': particion})
            for caso in casos:
                cliente.create_dataset_item(
                    dataset_name=nombre, id=caso['id'], input=caso,
                    metadata={'origen': caso.get('origen'), 'particion': particion})
                subidos[particion] += 1
        except Exception as e:
            if aviso:
                aviso('no se pudo sembrar {}: {}'.format(nombre, e))
    return {'taller': len(partes['taller']), 'reserva': len(partes['reserva']),
            'subidos': subidos, 'en_langfuse': cliente is not None}


def cargar(objetivo, particion, trazas=None, raiz=ESPEJO, aviso=None):
    """Los casos de una particion. Langfuse manda; el espejo salva la corrida."""
    rol = objetivo['rol']
    cliente = _cliente(trazas)
    if cliente is not None:
        try:
            dataset = cliente.get_dataset(nombre_dataset(rol, particion))
            casos = [dict(item.input) for item in dataset.items
                     if isinstance(item.input, dict)]
            if casos:
                escribir_espejo(rol, particion, casos, raiz)
                return casos, 'langfuse'
        except Exception as e:
            if aviso:
                aviso('Langfuse no sirvio los casos de {}: {}'.format(particion, e))
    return leer_espejo(rol, particion, raiz), 'espejo'
