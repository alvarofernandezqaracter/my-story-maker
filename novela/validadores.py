# §9 Inventario de validadores. Comprobaciones deterministas en codigo, con id
# VD-xx. No confundir con el agente validador de §5: aqui no hay criterio
# literario ni llamadas a modelos, solo reglas que se cumplen o no.
#
# Bloqueante: el artefacto no se usa. Aviso: se registra y el proceso sigue.
import math
import re

from .esquemas import comprobar_forma, SALIDAS, DIMENSIONES
from .util import numero_corto, redondear

BLOQ = 'bloqueante'
AVISO = 'aviso'


def _ok(id_validador):
    return {'id': id_validador, 'ok': True, 'severidad': None, 'detalles': []}


def _falla(id_validador, severidad, detalles):
    if isinstance(detalles, str):
        detalles = [detalles]
    return {'id': id_validador, 'ok': False, 'severidad': severidad,
            'detalles': list(detalles)}


class Resultado:
    """Resultado agregado de una tanda de comprobaciones."""

    def __init__(self, comprobaciones):
        self.comprobaciones = comprobaciones

    @property
    def bloqueantes(self):
        return [c for c in self.comprobaciones if not c['ok'] and c['severidad'] == BLOQ]

    @property
    def avisos(self):
        return [c for c in self.comprobaciones if not c['ok'] and c['severidad'] == AVISO]

    @property
    def ok(self):
        return not self.bloqueantes

    def incidencias(self):
        """Las incidencias en el formato que viaja al escritor en el reintento (§8)."""
        return [{
            'cita': '[{}]'.format(c['id']),
            'severidad': 'grave' if c['severidad'] == BLOQ else 'aviso',
            'sugerencia': '; '.join(c['detalles']),
        } for c in self.comprobaciones if not c['ok']]

    def resumen(self):
        return ['{} ({}): {}'.format(c['id'], c['severidad'], '; '.join(c['detalles']))
                for c in self.comprobaciones if not c['ok']]


# ---------------------------------------------------------------- VD-01, VD-02

def comprobar_salida_de_agente(rol, salida):
    """VD-01 la salida parsea y cumple el esquema; VD-02 obligatorios no vacios."""
    if not isinstance(salida, dict):
        return Resultado([
            _falla('VD-01', BLOQ, 'la salida no parsea como objeto'),
            _ok('VD-02'),
        ])

    esquema = SALIDAS.get(rol)
    if not esquema:
        raise ValueError('rol sin contrato de salida: {}'.format(rol))

    fallos = comprobar_forma(salida, esquema)
    ausentes = [f for f in fallos if 'obligatorio ausente' in f]
    forma = [f for f in fallos if 'obligatorio ausente' not in f]
    return Resultado([
        _falla('VD-01', BLOQ, forma) if forma else _ok('VD-01'),
        _falla('VD-02', BLOQ, ausentes) if ausentes else _ok('VD-02'),
    ])


# ---------------------------------------------------------------------- VD-03

def comprobar_referencias(rol, salida, conocidos):
    """VD-03 los ids referenciados existen en el canon. Arquitecto y cronista."""
    huerfanos = []

    if rol == 'arquitecto':
        # El arquitecto trae sus propios personajes: valen los que el mismo propone.
        propios = {p['id'] for p in salida.get('personajes') or []}
        for f in salida.get('capitulos') or []:
            for id_personaje in f.get('personajes') or []:
                if id_personaje not in propios and id_personaje not in conocidos['personajes']:
                    huerfanos.append('capitulo {}: personaje {}'.format(
                        f.get('numero'), id_personaje))

    if rol == 'cronista':
        for id_personaje in salida.get('personajes_presentes') or []:
            if id_personaje not in conocidos['personajes']:
                huerfanos.append('personajes_presentes: {}'.format(id_personaje))
        for c in salida.get('cambios_personaje') or []:
            if c['id'] not in conocidos['personajes']:
                huerfanos.append('cambios_personaje: {}'.format(c['id']))
        for e in salida.get('eventos') or []:
            for id_personaje in e.get('personajes') or []:
                if id_personaje not in conocidos['personajes']:
                    huerfanos.append('evento {}: personaje {}'.format(e['id'], id_personaje))
            if e.get('dato_id') and e['dato_id'] not in conocidos['datos']:
                huerfanos.append('evento {}: dato {}'.format(e['id'], e['dato_id']))

    return _falla('VD-03', BLOQ, huerfanos) if huerfanos else _ok('VD-03')


# ---------------------------------------------------------------------- VD-04

def comprobar_dossier(datos):
    """VD-04 todo dato historico lleva fuente y estado valido. Devuelve los malos."""
    malos = []
    for d in datos or []:
        sin_fuente = not d.get('fuente') or str(d['fuente']).strip() == ''
        estado_malo = d.get('estado') not in ('verificado', 'sin_verificar', 'inventado')
        # Un dato verificado tiene que apoyarse en algo que no sea la memoria del modelo.
        verificado_sin_respaldo = d.get('estado') == 'verificado' and d.get('fuente') == 'modelo'

        if sin_fuente or estado_malo or verificado_sin_respaldo:
            if sin_fuente:
                motivo = 'sin fuente'
            elif estado_malo:
                motivo = 'estado no valido: {}'.format(d.get('estado'))
            else:
                motivo = 'marcado verificado con fuente "modelo"'
            malos.append({'id': d.get('id'), 'motivo': motivo})

    if malos:
        comprobacion = _falla('VD-04', BLOQ,
                              ['{}: {}'.format(m['id'], m['motivo']) for m in malos])
    else:
        comprobacion = _ok('VD-04')
    comprobacion['malos'] = malos
    return comprobacion


# ---------------------------------------------------------------------- VD-05

def comprobar_eventos(eventos):
    """VD-05 evento de trama con capitulo; evento historico sin el."""
    malos = []
    for e in eventos or []:
        if e.get('tipo') == 'trama' and e.get('capitulo') is None:
            malos.append('{}: evento de trama sin capitulo'.format(e.get('id')))
        if e.get('tipo') == 'historico' and e.get('capitulo') is not None:
            malos.append('{}: evento historico con capitulo'.format(e.get('id')))
    return _falla('VD-05', BLOQ, malos) if malos else _ok('VD-05')


# ---------------------------------------------------------------------- VD-06

def comprobar_resumen_solo_si_aprobado(intento_aprobado):
    """VD-06 solo hay resumen si el capitulo esta aprobado."""
    if intento_aprobado:
        return _ok('VD-06')
    return _falla('VD-06', BLOQ,
                  'no hay intento aprobado: el resumen no puede entrar en el canon')


# ---------------------------------------------------------------------- VD-07

def comprobar_numero_de_capitulos(propuestos, pedidos, margenes):
    """VD-07 numero de capitulos dentro de los margenes de config."""
    minimo = math.floor(pedidos * margenes['capitulos_min'])
    maximo = math.ceil(pedidos * margenes['capitulos_max'])

    if minimo <= propuestos <= maximo:
        comprobacion = _ok('VD-07')
    else:
        comprobacion = _falla('VD-07', BLOQ, (
            'la escaleta trae {} capitulos y el margen para {} es [{}, {}]'
            .format(propuestos, pedidos, minimo, maximo)))
    comprobacion['margen'] = {'min': minimo, 'max': maximo}
    return comprobacion


# ---------------------------------------------------------------------- VD-08

def contar_palabras(texto):
    return len(re.findall(r'\S+', str(texto).strip()))


def contar_parrafos(texto):
    parrafos = re.split(r'\n\s*\n', str(texto))
    return len([p for p in (x.strip() for x in parrafos)
                if p != '' and not re.match(r'^#{1,6}\s', p)])


def comprobar_capitulo_redactado(texto, palabras_objetivo, margenes):
    """VD-08, la unica comprobacion de dos escalones y por eso lleva dos margenes.

    Dentro de palabras_aviso el texto vale y la desviacion viaja como aviso al
    reintento; pasado palabras_bloqueo no se gasta la llamada al validador.
    """
    palabras = contar_palabras(texto)
    parrafos = contar_parrafos(texto)
    desvio = (abs(palabras - palabras_objetivo) / palabras_objetivo
              if palabras_objetivo > 0 else 0)

    detalles = []
    severidad = None

    if parrafos < margenes['parrafos_min']:
        severidad = BLOQ
        detalles.append('{} parrafos, el minimo es {}'.format(
            parrafos, margenes['parrafos_min']))

    if desvio > margenes['palabras_bloqueo']:
        severidad = BLOQ
        detalles.append(
            '{} palabras frente a {} objetivo (desvio {:.0f}%, bloqueo en {}%)'.format(
                palabras, palabras_objetivo, redondear(desvio * 100, 0),
                numero_corto(margenes['palabras_bloqueo'] * 100)))
    elif desvio > margenes['palabras_aviso']:
        severidad = severidad or AVISO
        detalles.append(
            '{} palabras frente a {} objetivo (desvio {:.0f}%, aviso en {}%)'.format(
                palabras, palabras_objetivo, redondear(desvio * 100, 0),
                numero_corto(margenes['palabras_aviso'] * 100)))

    comprobacion = _falla('VD-08', severidad, detalles) if severidad else _ok('VD-08')
    comprobacion['palabras'] = palabras
    comprobacion['parrafos'] = parrafos
    return comprobacion


# ---------------------------------------------------------------------- VD-09

def comprobar_personajes_presentes(presentes, de_la_ficha):
    """VD-09 personajes presentes subconjunto de la ficha. Suele ser colado."""
    permitidos = set(de_la_ficha)
    colados = [i for i in (presentes or []) if i not in permitidos]
    if colados:
        return _falla('VD-09', BLOQ,
                      'personajes que no estan en la ficha: {}'.format(', '.join(colados)))
    return _ok('VD-09')


# ---------------------------------------------------------------------- VD-10

def comprobar_revisiones(revisiones):
    """VD-10 tres dimensiones, una vez cada una, nota entera 1-5."""
    detalles = []
    vistas = [r.get('dimension') for r in (revisiones or [])]

    for d in DIMENSIONES:
        veces = vistas.count(d)
        if veces != 1:
            detalles.append('dimension {} aparece {} veces, debe aparecer 1'.format(d, veces))

    for v in vistas:
        if v not in DIMENSIONES:
            detalles.append('dimension desconocida: {}'.format(v))

    for r in revisiones or []:
        nota = r.get('nota')
        if not isinstance(nota, int) or isinstance(nota, bool) or nota < 1 or nota > 5:
            detalles.append('{}: nota {} no es un entero entre 1 y 5'.format(
                r.get('dimension'), nota))

    return _falla('VD-10', BLOQ, detalles) if detalles else _ok('VD-10')


# ---------------------------------------------------------------------- VD-11

def comprobar_sin_bloqueantes_pendientes(resultados):
    """VD-11 ningun bloqueante pendiente al confirmar.

    La transaccion del canon vive en Canon.escritura_del_cronista; aqui se
    decide si se llega a abrir.
    """
    pendientes = []
    for r in resultados:
        if isinstance(r, Resultado):
            pendientes.extend(r.bloqueantes)
        elif not r['ok'] and r['severidad'] == BLOQ:
            pendientes.append(r)

    if pendientes:
        return _falla('VD-11', BLOQ, 'bloqueantes sin resolver: {}'.format(
            ', '.join(p['id'] for p in pendientes)))
    return _ok('VD-11')
