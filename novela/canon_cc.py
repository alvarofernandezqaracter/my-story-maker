# §21 Lector del canon en ficheros del camino delegado.
#
# El camino principal no tiene Python: orquesta una sesion de Claude Code y deja
# el canon en JSON bajo `novela-cc/`. Este fichero **solo lee**. No escribe una
# sola clave, y no por pudor: la regla de §21 dice que en ese canon escribe el
# orquestador y nadie mas, y la interfaz no es el orquestador.
#
# Su trabajo es dar a §19 la misma forma de datos que `canon.py` saca de SQLite,
# para que la pagina no tenga que saber por cual de los dos caminos mira.
import json
from pathlib import Path

from .gate import media as promedio
from .util import redondear

RAIZ = 'novela-cc'

# Las tres dimensiones de §8, siempre en este orden. Las notas viajan como
# diccionario en estado.json y como lista en la API, y el orden es el contrato.
DIMENSIONES = ('continuidad', 'anacronismos', 'logica_ritmo')

CAMPOS_BRIEF = ('epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo')


def _leer(ruta, por_defecto=None):
    """Un fichero del canon, o el valor de reposo si no esta.

    Que falte un fichero es normal: `dossier.json` no existe hasta que pasa el
    investigador. Que este roto no lo es, pero tampoco puede tumbar la pagina:
    la interfaz es un mirador y un JSON a medio escribir se ve como un hueco.
    """
    try:
        return json.loads(Path(ruta).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return por_defecto


def _notas_en_lista(notas):
    """El dict de notas de estado.json, en el orden de §8. None si falta alguna."""
    if not isinstance(notas, dict):
        return None
    valores = [notas.get(d) for d in DIMENSIONES]
    correctas = all(isinstance(v, int) and not isinstance(v, bool) for v in valores)
    return valores if correctas else None


class CanonCC:
    """El canon de `novela-cc/`, de solo lectura.

    Se construye barato y lee de disco en cada consulta: el orquestador escribe
    esos ficheros desde otra sesion mientras la pagina mira, asi que cachear
    seria ensenar el canon de hace un minuto.
    """

    def __init__(self, raiz=RAIZ):
        self.raiz = Path(raiz)

    # ---- rutas

    @property
    def dir_canon(self):
        return self.raiz / 'canon'

    def ruta_contexto(self, numero):
        return self.raiz / 'contexto' / 'cap-{:02d}.md'.format(numero)

    def ruta_retoques(self):
        return self.raiz / 'retoques.md'

    @property
    def existe(self):
        return (self.dir_canon / 'estado.json').is_file() or (
            self.dir_canon / 'brief.json').is_file()

    # ---- ficheros sueltos

    def brief(self):
        bruto = _leer(self.dir_canon / 'brief.json')
        if not isinstance(bruto, dict):
            return None
        return {c: bruto.get(c) for c in CAMPOS_BRIEF}

    def _estado_bruto(self):
        bruto = _leer(self.dir_canon / 'estado.json', {})
        return bruto if isinstance(bruto, dict) else {}

    def estado(self):
        return self._estado_bruto().get('estado')

    def actualizado(self):
        return self._estado_bruto().get('actualizado')

    def datos(self):
        return (_leer(self.dir_canon / 'dossier.json', {}) or {}).get('datos') or []

    def personajes(self):
        return (_leer(self.dir_canon / 'personajes.json', {}) or {}).get('personajes') or []

    def escaleta(self):
        return (_leer(self.dir_canon / 'escaleta.json', {}) or {}).get('capitulos') or []

    def hilos(self):
        return (_leer(self.dir_canon / 'hilos.json', {}) or {}).get('hilos') or []

    def hilos_vivos(self):
        """La deuda de la novela: lo que un capitulo abrio y ninguno cerro (§7)."""
        return [h for h in self.hilos() if h.get('cerrado_en') is None]

    def eventos(self):
        """La cronologia, ordenada por fecha de ficcion y luego por capitulo."""
        eventos = (_leer(self.dir_canon / 'timeline.json', {}) or {}).get('eventos') or []
        return sorted(eventos, key=lambda e: (str(e.get('fecha') or ''),
                                              e.get('capitulo') or 0))

    def resumen(self, numero):
        return _leer(self.dir_canon / 'resumenes' / 'cap-{:02d}.json'.format(numero))

    def resumenes(self):
        salida = []
        for fichero in sorted((self.dir_canon / 'resumenes').glob('cap-*.json')):
            bruto = _leer(fichero)
            if isinstance(bruto, dict):
                salida.append(bruto)
        return sorted(salida, key=lambda r: r.get('capitulo') or 0)

    # ---- capitulos e intentos

    def ficha_estado(self, numero):
        """Lo que estado.json guarda de un capitulo, con lo que falte a su valor
        de reposo. Las claves del JSON son cadenas, pero se acepta el entero por
        si el orquestador lo escribio asi.
        """
        capitulos = self._estado_bruto().get('capitulos') or {}
        bruto = capitulos.get(str(numero)) or capitulos.get(numero) or {}
        return {
            'estado': bruto.get('estado') or 'pendiente',
            'intento_aprobado': bruto.get('intento_aprobado'),
            'intentos': bruto.get('intentos') or [],
            'contexto': bruto.get('contexto') or {},
        }

    def intentos(self, numero):
        return self.ficha_estado(numero)['intentos']

    def intento_aprobado(self, numero):
        ficha = self.ficha_estado(numero)
        k = ficha['intento_aprobado']
        return next((i for i in ficha['intentos'] if i.get('intento') == k), None)

    def texto(self, numero):
        """El texto del intento aprobado, si el fichero sigue donde dice el canon."""
        aprobado = self.intento_aprobado(numero)
        if not aprobado or not aprobado.get('ruta'):
            return None, None
        ruta = Path(aprobado['ruta'])
        if not ruta.is_absolute():
            # Las rutas del canon se escriben desde la raiz del repositorio.
            ruta = Path.cwd() / ruta
        if not ruta.is_file():
            return None, aprobado['ruta']
        return ruta.read_text(encoding='utf-8'), aprobado['ruta']

    def contexto(self, numero):
        ruta = self.ruta_contexto(numero)
        return (ruta.read_text(encoding='utf-8') if ruta.is_file() else None,
                ruta.as_posix())

    def retoques(self):
        ruta = self.ruta_retoques()
        return (ruta.read_text(encoding='utf-8') if ruta.is_file() else None,
                ruta.as_posix())


# ------------------------------------------------------- auditoria del gate

def auditar_gate(intento, config_gate):
    """Rehace la cuenta del gate (§8) sobre lo que el orquestador dejo escrito.

    §21 dice que el punto mas debil del camino delegado es que la suma del gate
    la hace un modelo. Esto es lo unico que la interfaz puede hacer al respecto:
    coger las tres notas y el recuento de graves del canon, aplicar la formula
    con los umbrales de §12 y comparar el veredicto con el que se guardo.

    No corrige nada -el canon es la verdad, aunque se equivoque- pero deja la
    discrepancia a la vista, que es justo el dato que este camino existe para dar.
    """
    notas = _notas_en_lista(intento.get('notas'))
    if not notas:
        return None
    graves = intento.get('graves')
    graves = graves if isinstance(graves, int) and not isinstance(graves, bool) else 0

    minima = min(notas)
    media = redondear(promedio(notas), 2)
    motivos = []
    if minima < config_gate['nota_minima']:
        motivos.append('nota minima {} por debajo de {}'.format(
            minima, config_gate['nota_minima']))
    if media < config_gate['media_minima']:
        motivos.append('media {:.2f} por debajo de {}'.format(
            media, config_gate['media_minima']))
    if graves:
        motivos.append('{} incidencia(s) grave(s)'.format(graves))

    aprueba = not motivos
    guardado = intento.get('aprueba')
    return {
        'minima': minima,
        'media': media,
        'graves': graves,
        'aprueba': aprueba,
        'motivos': motivos,
        # Lo que el orquestador escribio, para poder mirar las dos cosas.
        'minima_canon': intento.get('minima'),
        'media_canon': intento.get('media'),
        'aprueba_canon': guardado,
        'cuadra': (guardado is None) or bool(guardado) == aprueba,
    }


def operacion(intento, config_gate, cuenta=None):
    """La operacion entera en una linea, que es lo que §21 obliga a imprimir."""
    cuenta = cuenta if cuenta is not None else auditar_gate(intento, config_gate)
    if not cuenta:
        return 'VD-08: descartado antes de llamar a los validadores'
    notas = _notas_en_lista(intento.get('notas')) or []
    return 'min({}) = {} >= {} · media {:.2f} >= {} · {} grave(s) -> {}'.format(
        '/'.join(str(n) for n in notas), cuenta['minima'], config_gate['nota_minima'],
        cuenta['media'], config_gate['media_minima'], cuenta['graves'],
        'aprueba' if cuenta['aprueba'] else 'rechaza')


def notas_en_lista(notas):
    return _notas_en_lista(notas)


def media_de(notas):
    lista = _notas_en_lista(notas)
    return redondear(promedio(lista), 2) if lista else None
