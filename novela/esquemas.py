# Contratos de entrada/salida de los seis agentes de §5. No son un esquema JSON
# completo: solo lo que VD-01 y VD-02 necesitan para decidir si una propuesta
# parsea y trae sus campos obligatorios. El fondo no se juzga aqui.

DIMENSIONES = ['continuidad', 'anacronismos', 'logica_ritmo']
CATEGORIAS_DATO = ['vestimenta', 'politica', 'comida', 'lenguaje', 'otro']
ESTADOS_DATO = ['verificado', 'sin_verificar', 'inventado']
ROLES_PERSONAJE = ['protagonista', 'secundario', 'figurante']
TIPOS_EVENTO = ['trama', 'historico']
SEVERIDADES = ['grave', 'aviso']
TIPOS_RETOQUE = ['arco', 'promesa', 'ritmo', 'personaje']

ESTADOS_PROYECTO = [
    'borrador', 'investigado', 'estructurado', 'escribiendo', 'bloqueado', 'escrito', 'editado',
]
ESTADOS_FICHA = ['pendiente', 'en_curso', 'aprobado', 'bloqueado']
ESTADOS_REDACTADO = ['propuesto', 'aprobado', 'descartado']

TEXTO = {'tipo': 'texto'}
ENTERO = {'tipo': 'entero'}


def lista(de):
    return {'tipo': 'lista', 'de': de}


def enumerado(valores):
    return {'tipo': 'enum', 'valores': valores}


def opcional(definicion):
    return {**definicion, 'opcional': True}


DATO = {
    'id': TEXTO, 'categoria': enumerado(CATEGORIAS_DATO), 'dato': TEXTO,
    'fuente': TEXTO, 'estado': enumerado(ESTADOS_DATO), 'etiquetas': lista(TEXTO),
}

PERSONAJE = {
    'id': TEXTO, 'nombre': TEXTO, 'rol': enumerado(ROLES_PERSONAJE), 'voz': TEXTO,
    'motivacion': TEXTO, 'arco': TEXTO, 'ubicacion': TEXTO,
    'sabe': opcional(lista(TEXTO)),
}

FICHA_CAPITULO = {
    'numero': ENTERO, 'titulo': TEXTO, 'acto': ENTERO, 'sinopsis': TEXTO, 'fecha': TEXTO,
    'personajes': lista(TEXTO), 'etiquetas': lista(TEXTO), 'objetivo': TEXTO,
    'palabras_objetivo': ENTERO,
}

INCIDENCIA = {
    'cita': TEXTO, 'severidad': enumerado(SEVERIDADES), 'sugerencia': TEXTO,
}

BLOQUE_REVISION = {
    'dimension': enumerado(DIMENSIONES), 'nota': ENTERO,
    'incidencias': opcional(lista(INCIDENCIA)),
}

EVENTO = {
    'id': TEXTO, 'tipo': enumerado(TIPOS_EVENTO), 'fecha': TEXTO, 'descripcion': TEXTO,
    'capitulo': opcional(ENTERO),
    'personajes': opcional(lista(TEXTO)),
    'dato_id': opcional(TEXTO),
}

CAMBIO_PERSONAJE = {
    'id': TEXTO,
    'ubicacion': opcional(TEXTO),
    'sabe': opcional(lista(TEXTO)),
}

RETOQUE = {
    'id': TEXTO, 'tipo': enumerado(TIPOS_RETOQUE), 'capitulos': lista(ENTERO),
    'descripcion': TEXTO, 'severidad': enumerado(SEVERIDADES),
}

# Salida esperada de cada rol. La clave es el rol de §5.
SALIDAS = {
    'investigador': {'datos': lista(DATO)},
    'arquitecto': {'personajes': lista(PERSONAJE), 'capitulos': lista(FICHA_CAPITULO)},
    'escritor': {'texto': TEXTO, 'faltantes': opcional(lista(TEXTO))},
    'validador': {'revisiones': lista(BLOQUE_REVISION)},
    'cronista': {
        'resumen': TEXTO,
        'hilos_abiertos': lista(TEXTO), 'hilos_cerrados': lista(TEXTO),
        'personajes_presentes': lista(TEXTO),
        'cambios_personaje': opcional(lista(CAMBIO_PERSONAJE)),
        'eventos': opcional(lista(EVENTO)),
    },
    'editor_global': {'retoques': lista(RETOQUE)},
}

# En modo separado el validador devuelve un bloque por llamada.
SALIDA_VALIDADOR_DIMENSION = {'revisiones': lista(BLOQUE_REVISION)}


def comprobar_forma(valor, esquema, camino=''):
    """Comprueba forma (VD-01) y obligatoriedad (VD-02). Devuelve lista de fallos."""
    if not isinstance(valor, dict):
        return ['{}: se esperaba un objeto'.format(camino or 'raiz')]

    fallos = []
    for clave, definicion in esquema.items():
        ruta = '{}.{}'.format(camino, clave) if camino else clave
        v = valor.get(clave)
        if v is None:
            if not definicion.get('opcional'):
                fallos.append('{}: campo obligatorio ausente'.format(ruta))
            continue
        fallos.extend(_comprobar_valor(v, definicion, ruta))
    return fallos


def _comprobar_valor(v, definicion, ruta):
    fallos = []
    tipo = definicion.get('tipo')

    if tipo == 'texto':
        if not isinstance(v, str) or v.strip() == '':
            fallos.append('{}: texto vacio o no textual'.format(ruta))
    elif tipo == 'entero':
        if not isinstance(v, int) or isinstance(v, bool):
            fallos.append('{}: se esperaba un entero'.format(ruta))
    elif tipo == 'enum':
        if v not in definicion['valores']:
            fallos.append('{}: "{}" no esta en [{}]'.format(
                ruta, v, ', '.join(definicion['valores'])))
    elif tipo == 'lista':
        if not isinstance(v, list):
            return ['{}: se esperaba una lista'.format(ruta)]
        de = definicion['de']
        for i, elemento in enumerate(v):
            sub = '{}[{}]'.format(ruta, i)
            if 'tipo' in de:
                fallos.extend(_comprobar_valor(elemento, de, sub))
            else:
                fallos.extend(comprobar_forma(elemento, de, sub))
    else:
        fallos.extend(comprobar_forma(v, definicion, ruta))
    return fallos
