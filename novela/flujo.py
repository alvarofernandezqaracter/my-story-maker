# §4 Arquitectura y flujo, §8 loop de capitulo y gate, §11 editor global.
# Tres tramos: preparacion (una vez), loop de capitulo (una vez por capitulo) y
# cierre (una vez). El canon esta en medio de todos y es el unico punto de
# contacto: los agentes nunca se pasan datos entre si por fuera del canon o del
# paquete de contexto.
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agentes import ParadaDelProceso
from .contexto import generar_contexto
from .esquemas import DIMENSIONES
from .gate import gate, mejor_intento, incidencias_ordenadas, media, notas
from .util import redondear
from .validadores import (
    Resultado,
    comprobar_dossier, comprobar_referencias, comprobar_eventos,
    comprobar_numero_de_capitulos, comprobar_capitulo_redactado,
    comprobar_personajes_presentes, comprobar_revisiones,
    comprobar_resumen_solo_si_aprobado, comprobar_sin_bloqueantes_pendientes,
)

CARPETA_CAPITULOS = 'capitulos'


def ruta_de_intento(capitulo, intento, carpeta=CARPETA_CAPITULOS):
    # El par capitulo e intento identifica cada fichero, asi que repetir un
    # intento sobrescribe en lugar de duplicar (§13).
    return str(Path(carpeta) / '{:03d}-i{}.md'.format(capitulo, intento))


def _escribir(ruta, texto):
    # newline='\n' explicito: sin el, Windows mete CRLF y los capitulos dejan de
    # ser byte a byte los mismos que en Linux.
    with open(ruta, 'w', encoding='utf-8', newline='\n') as fichero:
        fichero.write(texto)


def _traza(diario, tipo, datos):
    """Registro de lo que va pasando, para que la CLI lo cuente sin adivinar."""
    diario.append({'tipo': tipo, **datos})
    return diario[-1]


# ============================================================ PREPARACION

def preparar(canon, agentes, config, diario=None):
    diario = diario if diario is not None else []
    proyecto = canon.proyecto()
    if not proyecto:
        raise ParadaDelProceso('no hay brief: usa "novela brief" antes de preparar')

    brief = {
        'epoca': proyecto['epoca'],
        'premisa': proyecto['premisa'],
        'tono': proyecto['tono'],
        'capitulos': proyecto['capitulos'],
        'palabras_por_capitulo': proyecto['palabras_por_capitulo'],
    }

    # ---- Investigador. VD-04 corre antes de habilitar al arquitecto (§9).
    if proyecto['estado'] == 'borrador':
        respuesta = agentes.pedir(
            'investigador',
            {'brief': brief, 'busqueda_web': config['busqueda_web']},
            lambda s: [comprobar_dossier(s['datos'])],
        )
        salida = respuesta['salida']
        canon.guardar_datos(salida['datos'])
        canon.marcar_estado('investigado')
        _traza(diario, 'dossier', {'datos': len(salida['datos'])})

    # ---- Arquitecto. Necesita el dossier cerrado.
    if canon.estado() == 'investigado':
        dossier = canon.datos()
        conocidos = canon.ids_conocidos()
        respuesta = agentes.pedir(
            'arquitecto',
            {'brief': brief, 'dossier': dossier},
            lambda s: [
                comprobar_numero_de_capitulos(
                    len(s['capitulos']), brief['capitulos'], config['margenes']),
                comprobar_referencias('arquitecto', s, conocidos),
            ],
        )
        salida = respuesta['salida']
        canon.guardar_personajes(salida['personajes'])
        canon.guardar_fichas(salida['capitulos'])
        canon.marcar_estado('estructurado')
        _traza(diario, 'escaleta', {
            'personajes': len(salida['personajes']),
            'capitulos': len(salida['capitulos']),
        })

    return {'estado': canon.estado(), 'diario': diario}


# ======================================================= LOOP DE CAPITULO

def escribir_capitulo(canon, agentes, config, numero, diario=None):
    """Un capitulo se da por bueno cuando pasa el gate, no cuando el escritor
    termina. Todo lo de aqui es codigo salvo las cuatro llamadas a agentes.
    """
    diario = diario if diario is not None else []
    canon.marcar_ficha(numero, 'en_curso')
    if canon.estado() == 'estructurado':
        canon.marcar_estado('escribiendo')

    paquete = generar_contexto(canon, numero, config)
    if not paquete['cabe']:
        # §7: si no cabe ni recortando, el capitulo se bloquea en lugar de
        # escribirse con el contexto mutilado.
        canon.marcar_ficha(numero, 'bloqueado')
        canon.marcar_estado('bloqueado')
        _traza(diario, 'bloqueado', {
            'capitulo': numero, 'motivo': 'el paquete de contexto no cabe'})
        return {'aprobado': False, 'motivo': 'contexto'}

    if paquete['recortes']:
        _traza(diario, 'recorte', {'capitulo': numero, 'bloques': paquete['recortes']})

    ficha = paquete['bloques']['encargo']
    personajes = paquete['bloques']['personajes']
    Path(CARPETA_CAPITULOS).mkdir(parents=True, exist_ok=True)

    incidencias = []
    texto_previo = None

    for intento in range(1, config['gate']['max_intentos'] + 1):
        es_ultimo = intento == config['gate']['max_intentos']

        # ---- Escritor
        redaccion = agentes.pedir('escritor', {
            'paquete': paquete['texto'],
            'encargo': ficha,
            'personajes': personajes,
            'texto_previo': texto_previo,
            'incidencias': incidencias,
            'intento': intento,
        })['salida']

        ruta = ruta_de_intento(numero, intento)
        _escribir(ruta, redaccion['texto'])

        # ---- VD-08, antes del validador
        det = comprobar_capitulo_redactado(
            redaccion['texto'], ficha['palabras_objetivo'], config['margenes'])
        canon.guardar_intento(
            capitulo=numero,
            intento=intento,
            ruta=ruta,
            palabras=det['palabras'],
            faltantes=redaccion.get('faltantes') or [],
        )
        resultado_det = Resultado([det])

        if resultado_det.bloqueantes:
            # VD-08 en su escalon de bloqueo: se reintenta la generacion sin gastar
            # la llamada al agente validador, y el reintento va de cero.
            _traza(diario, 'vd08', {
                'capitulo': numero, 'intento': intento, 'detalles': det['detalles']})
            canon.marcar_intento(numero, intento, 'descartado')
            incidencias = resultado_det.incidencias()
            texto_previo = None
            continue

        # ---- Validador. Una llamada, o tres si validador.modo es separado (§5).
        revisiones = _validar(agentes, config, redaccion['texto'], paquete, ficha, intento)
        canon.guardar_revisiones(numero, intento, revisiones)

        # ---- Gate. Solo se calcula sobre revisiones que ya pasaron VD-10 (§9).
        veredicto = gate(revisiones, config['gate'])
        _traza(diario, 'gate', {
            'capitulo': numero,
            'intento': intento,
            'aprueba': veredicto['aprueba'],
            'notas': notas(revisiones),
            'media': redondear(veredicto['media'], 2),
            'motivos': veredicto['motivos'],
        })

        if veredicto['aprueba']:
            canon.fijar_intento_aprobado(numero, intento)
            _volcar_en_el_canon(
                canon, agentes, numero, redaccion['texto'], ficha, personajes, diario)
            return {'aprobado': True, 'intento': intento, 'revisiones': revisiones}

        # §8: incidencias del validador mas los avisos deterministas.
        incidencias = incidencias_ordenadas(revisiones) + resultado_det.incidencias()
        # Su propio texto en todos los intentos menos el ultimo: ahi se le pide
        # arreglo quirurgico. El ultimo va desde cero.
        texto_previo = None if es_ultimo else redaccion['texto']

    # ---- Al agotar los intentos
    todos = canon.intentos(numero)
    mejor = mejor_intento(todos)
    for i in todos:
        canon.marcar_intento(numero, i['intento'], 'propuesto' if i is mejor else 'descartado')
    canon.marcar_ficha(numero, 'bloqueado')
    canon.marcar_estado('bloqueado')
    _traza(diario, 'bloqueado', {
        'capitulo': numero,
        'motivo': 'agotados los {} intentos'.format(config['gate']['max_intentos']),
        'conservado': mejor['ruta'] if mejor else None,
    })
    return {'aprobado': False, 'motivo': 'intentos'}


def _validar(agentes, config, texto, paquete, encargo, intento):
    """Una llamada al validador, o tres en paralelo si el modo es separado (§5).

    VD-10 se aplica siempre al conjunto de las tres dimensiones, venga de donde
    venga, y su fallo reintenta la llamada al validador, no al escritor (§9).
    """
    base = {'texto': texto, 'paquete': paquete['texto'], 'encargo': encargo, 'intento': intento}

    if config['validador']['modo'] != 'separado':
        return agentes.pedir(
            'validador', base, lambda s: [comprobar_revisiones(s['revisiones'])],
        )['salida']['revisiones']

    # Modo separado: cada llamada trae un bloque, y solo se comprueba ese bloque.
    def una(dimension):
        def comprobar(s):
            propias = [r for r in s['revisiones'] if r['dimension'] == dimension]
            resto = [{'dimension': d, 'nota': 3} for d in DIMENSIONES if d != dimension]
            return [comprobar_revisiones(propias + resto)]
        return agentes.pedir('validador', {**base, 'dimension': dimension}, comprobar)

    with ThreadPoolExecutor(max_workers=len(DIMENSIONES)) as ejecutor:
        partes = list(ejecutor.map(una, DIMENSIONES))

    todas = [r for p in partes for r in p['salida']['revisiones']]
    revisiones = []
    for d in DIMENSIONES:
        encontrada = next((r for r in todas if r['dimension'] == d), None)
        if encontrada:
            revisiones.append(encontrada)

    vd10 = comprobar_revisiones(revisiones)
    if not vd10['ok']:
        raise ParadaDelProceso(
            'las tres llamadas al validador no componen tres bloques validos',
            vd10['detalles'])
    return revisiones


def _volcar_en_el_canon(canon, agentes, numero, texto, ficha, personajes, diario):
    """Unica escritura en el canon dentro del loop: el cronista convierte el
    capitulo aprobado en resumen y en cambios de ficha, y el harness lo persiste
    en una transaccion (VD-11).
    """
    conocidos = canon.ids_conocidos()
    respuesta = agentes.pedir(
        'cronista',
        {'texto': texto, 'ficha': ficha, 'personajes': personajes},
        lambda s: [
            comprobar_personajes_presentes(s['personajes_presentes'], ficha['personajes']),
            comprobar_referencias('cronista', s, conocidos),
            comprobar_eventos(s.get('eventos')),
            comprobar_resumen_solo_si_aprobado(canon.intento_aprobado(numero)),
        ],
    )
    propuesta = respuesta['salida']

    vd11 = comprobar_sin_bloqueantes_pendientes(respuesta['comprobaciones'])
    if not vd11['ok']:
        raise ParadaDelProceso(
            'VD-11 impide confirmar la escritura del cronista', vd11['detalles'])

    canon.escritura_del_cronista(numero, propuesta)
    _traza(diario, 'canon', {
        'capitulo': numero,
        'hilos_abiertos': len(propuesta['hilos_abiertos']),
        'hilos_cerrados': len(propuesta['hilos_cerrados']),
        'eventos': len(propuesta.get('eventos') or []),
    })


# ================================================================== CIERRE

def cerrar(canon, agentes, ruta='retoques.md', diario=None):
    """§11. Corre una sola vez, cuando el proyecto entra en escrito, y fuera del
    loop. Lee los resumenes, nunca el texto. La lista se guarda como retoques.md
    junto al canon, no dentro: el canon es la verdad de la novela escrita y esto
    es una lista de tareas.
    """
    diario = diario if diario is not None else []
    salida = agentes.pedir('editor_global', {
        'resumenes': canon.resumenes(),
        'escaleta': canon.fichas(),
        'personajes': canon.personajes(),
        'hilos_vivos': canon.hilos_vivos(),
    })['salida']

    _escribir(ruta, _render_retoques(salida['retoques'], canon))
    canon.marcar_estado('editado')
    _traza(diario, 'retoques', {'total': len(salida['retoques']), 'ruta': ruta})
    return {'retoques': salida['retoques'], 'ruta': ruta, 'diario': diario}


def _render_retoques(retoques, canon):
    proyecto = canon.proyecto()
    lineas = [
        '# Retoques finales',
        '',
        'Lista del editor global sobre {} capitulos aprobados.'.format(
            len(canon.resumenes())),
        'El editor no aplica nada: decides tu que vale y lo aplicas editando los capitulos.',
        '',
        '- Epoca: {}'.format(proyecto['epoca']),
        '- Tono: {}'.format(proyecto['tono']),
        '',
    ]
    for r in retoques:
        lineas.append('## {} — {} ({})'.format(r['id'], r['tipo'], r['severidad']))
        lineas.append('Capitulos: {}'.format(
            ', '.join(str(c) for c in r['capitulos']) or '—'))
        lineas.append('')
        lineas.append(r['descripcion'])
        lineas.append('')
    if not retoques:
        lineas.append('Sin retoques. Revisa si el cronista esta registrando hilos.')
    return '\n'.join(lineas)


# ============================================== ORQUESTACION Y REANUDACION

def siguiente_capitulo(canon):
    """El primer capitulo que no esta aprobado."""
    return next((f for f in canon.fichas() if f['estado'] != 'aprobado'), None)


def reanudar(canon, agentes, config, diario=None):
    """§13. Un unico comando reanudar, sin argumentos: lee el estado del proyecto,
    localiza el primer capitulo no aprobado y sigue desde ahi. Reanudar no
    desbloquea: mientras el proyecto siga en bloqueado, vuelve a parar en el
    mismo capitulo.
    """
    diario = diario if diario is not None else []
    proyecto = canon.proyecto()
    if not proyecto:
        raise ParadaDelProceso('no hay brief que reanudar')

    if proyecto['estado'] == 'bloqueado':
        bloqueado = next((f for f in canon.fichas() if f['estado'] == 'bloqueado'), None)
        _traza(diario, 'parada', {
            'motivo': 'el proyecto esta bloqueado y reanudar no desbloquea',
            'capitulo': bloqueado['numero'] if bloqueado else None,
        })
        return {'estado': 'bloqueado', 'diario': diario}

    if proyecto['estado'] in ('borrador', 'investigado'):
        preparar(canon, agentes, config, diario)

    # Los intentos huerfanos de una caida se descartan al relanzar (§13).
    for f in canon.fichas():
        if f['estado'] == 'aprobado':
            continue
        for i in canon.intentos(f['numero']):
            if i['estado'] == 'propuesto':
                canon.marcar_intento(f['numero'], i['intento'], 'descartado')

    siguiente = siguiente_capitulo(canon)
    while siguiente:
        res = escribir_capitulo(canon, agentes, config, siguiente['numero'], diario)
        if not res['aprobado']:
            return {'estado': 'bloqueado', 'capitulo': siguiente['numero'], 'diario': diario}
        siguiente = siguiente_capitulo(canon)

    canon.marcar_estado('escrito')
    cierre = cerrar(canon, agentes, diario=diario)
    return {'estado': canon.estado(), 'retoques': cierre['retoques'], 'diario': diario}
