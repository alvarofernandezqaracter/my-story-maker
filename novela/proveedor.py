# Modo de ejecucion real (§12): las llamadas van a la API de Claude con el
# SDK oficial. El SDK se importa de forma perezosa para que el modo simulado,
# que es el de por defecto, no necesite ninguna dependencia instalada.
#
# §13: ante un error del proveedor se reintenta la llamada una vez; si vuelve a
# fallar, el proceso para y deja el estado escrito. No hay backoff ni politica
# de reintentos finos, y es deliberado.
import json

MAX_TOKENS = 32000

_cliente = None


def _cliente_perezoso():
    global _cliente
    if _cliente is None:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                'el modo real necesita el SDK oficial: pip install anthropic'
                ' ({})'.format(e)) from e
        # La credencial no vive en config.json: sale del entorno (§12).
        _cliente = anthropic.Anthropic()
    return _cliente


def _instruccion_de_formato(rol):
    """El contrato de salida se pide en el prompt y lo verifica VD-01 al recibirlo.

    Si el modelo devuelve algo que no parsea, el harness reintenta la llamada una
    vez y para: ese camino ya esta previsto en §9.
    """
    return '\n'.join([
        '',
        '# Formato de salida',
        '',
        'Responde unica y exclusivamente con un objeto JSON valido para el rol'
        ' {},'.format(rol),
        'sin texto antes ni despues y sin vallas de codigo. El harness lo parsea tal cual.',
    ])


def extraer_json(texto):
    """Extrae el primer objeto JSON del texto, tolerando vallas de codigo."""
    limpio = str(texto).strip()
    if limpio.lower().startswith('```json'):
        limpio = limpio[7:]
    elif limpio.startswith('```'):
        limpio = limpio[3:]
    limpio = limpio.lstrip()
    if limpio.endswith('```'):
        limpio = limpio[:-3]
    limpio = limpio.strip()

    try:
        return json.loads(limpio)
    except ValueError:
        inicio = limpio.find('{')
        fin = limpio.rfind('}')
        if inicio == -1 or fin <= inicio:
            raise ValueError('la respuesta del modelo no contiene un objeto JSON') from None
        return json.loads(limpio[inicio:fin + 1])


def llamar_al_proveedor(rol, modelo, instrucciones, entrada):
    cliente = _cliente_perezoso()

    with cliente.messages.stream(
        model=modelo,
        max_tokens=MAX_TOKENS,
        system=instrucciones + _instruccion_de_formato(rol),
        thinking={'type': 'adaptive'},
        output_config={'effort': 'high'},
        messages=[{'role': 'user',
                   'content': json.dumps(entrada, indent=2, ensure_ascii=False)}],
    ) as flujo:
        mensaje = flujo.get_final_message()

    if mensaje.stop_reason == 'refusal':
        categoria = getattr(mensaje.stop_details, 'category', None) or 'sin categoria'
        raise RuntimeError(
            'el modelo declino la peticion del rol {}: {}'.format(rol, categoria))

    texto = ''.join(b.text for b in mensaje.content if b.type == 'text')
    return {'salida': extraer_json(texto), 'uso': mensaje.usage}
