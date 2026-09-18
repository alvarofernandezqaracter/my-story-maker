# §3 de AUTOAPRENDIZAJE.md. Lo que se mide de la salida de un rol.
#
# Una metrica es una funcion de una corrida y su caso a un numero. Nada mas.
# **Ninguna se puntua a ojo**: o la calcula este fichero, o la pone un juez de
# Langfuse. Un numero que depende de que alguien lo mire no se puede correr
# veinte veces seguidas, que es justo lo que hace el banco.
#
# Las guardias que miran la forma de la salida no se inventan aqui: son los
# `VD-xx` de §9 de SPEC.md, que ya son comprobaciones deterministas sobre lo que
# devuelve un rol. Reimplementarlas con otro criterio seria tener dos verdades
# sobre el mismo JSON.
import json
import math
import re

# Los conjuntos cerrados del dossier (§3 de SPEC.md). Viven aqui porque VD-04
# los necesita y no son un umbral que se toque: son el esquema.
CATEGORIAS = ('vestimenta', 'politica', 'comida', 'lenguaje', 'otro')
ESTADOS_DATO = ('verificado', 'sin_verificar', 'inventado')

# Las tres dimensiones de §9, siempre estas y en este orden.
DIMENSIONES = ('continuidad', 'anacronismos', 'logica_ritmo')

VALLA = re.compile(r'^\s*```(?:json)?\s*|\s*```\s*$')


def tokens_estimados(texto):
    """Tokens de un texto, a ojo pero siempre con el mismo ojo.

    Cuatro caracteres por token. Es una estimacion y no pretende otra cosa: lo
    que el banco compara son dos candidatos medidos con esta misma regla, y para
    eso lo que hace falta no es exactitud sino que la regla no cambie. Contar de
    verdad exigiria el tokenizador del proveedor, que es una dependencia y una
    llamada mas por candidato.
    """
    return max(1, math.ceil(len(texto or '') / 4))


def _primer_objeto(texto):
    """El primer objeto JSON completo que haya dentro de un texto.

    Recorre contando llaves y saltandose las que van dentro de una cadena, que
    es lo minimo para no cortar por un `{` que forma parte de un dato.
    """
    inicio = texto.find('{')
    if inicio < 0:
        return None
    profundidad, en_cadena, escapado = 0, False, False
    for i in range(inicio, len(texto)):
        c = texto[i]
        if escapado:
            escapado = False
            continue
        if c == '\\':
            escapado = True
        elif c == '"':
            en_cadena = not en_cadena
        elif not en_cadena:
            if c == '{':
                profundidad += 1
            elif c == '}':
                profundidad -= 1
                if profundidad == 0:
                    return texto[inicio:i + 1]
    return None


def json_de(texto):
    """El JSON que devuelve un rol, o None si no lo devolvio.

    Tolera las vallas de codigo y el preambulo que el modelo pone a veces aunque
    su prompt se lo prohiba. **Esa desobediencia no se perdona, se mide aparte**:
    la forma es VD-01 y tiene su propia metrica. Si esta funcion fuera estricta,
    un "Aqui tienes el dossier:" dejaria a cero todas las metricas de contenido y
    el banco no sabria distinguir un prompt charlatan de uno que no trabaja.
    """
    crudo = (texto or '').strip()
    if not crudo:
        return None
    for intento in (crudo, VALLA.sub('', crudo), _primer_objeto(crudo)):
        if not intento:
            continue
        try:
            valor = json.loads(intento)
        except ValueError:
            continue
        return valor if isinstance(valor, (dict, list)) else None
    return None


def palabras(texto):
    return len((texto or '').split())


def parrafos(texto):
    return len([b for b in re.split(r'\n\s*\n', texto or '') if b.strip()])


# --- las metricas, una funcion por nombre -----------------------------------
# Todas reciben (corrida, caso, config) y devuelven un numero. Un None significa
# "esta corrida no puede dar este numero", y el agregado lo descarta en vez de
# contarlo como cero, que se leeria como un exito.

def _tokens_rol(corrida, caso, config):
    """Lo que cuesta el rol, sin el arnes que lo rodea.

    Es la suma del prompt que se le monto -contado en local, asi que no lo mueve
    la cache- y de lo que genero de verdad. **No incluye el preambulo de Claude
    Code**, que son decenas de miles de tokens iguales para todos los candidatos:
    dejarlo dentro no cambiaria quien gana, pero convertiria una mejora del 40%
    del prompt en una del 2% del total, y ningun margen distinguiria eso del
    ruido.
    """
    return corrida.get('tokens_prompt', 0) + corrida.get('tokens_salida', 0)


def _tokens_salida(corrida, caso, config):
    return corrida.get('tokens_salida')


def _tokens_prompt(corrida, caso, config):
    return corrida.get('tokens_prompt')


def _coste_usd(corrida, caso, config):
    """Lo que Claude Code dice que costo la sesion entera.

    Informativo y no comparable entre candidatos: lo mueve la cache, que depende
    de lo que corriera antes y no del prompt que se esta midiendo.
    """
    return corrida.get('coste_usd')


def _segundos(corrida, caso, config):
    return corrida.get('segundos')


def _palabras(corrida, caso, config):
    return palabras(corrida.get('salida'))


def _parrafos(corrida, caso, config):
    return parrafos(corrida.get('salida'))


def _desvio_palabras(corrida, caso, config):
    """Cuanto se aleja el capitulo de lo que pedia el brief, en tanto por uno.

    Sin signo: pasarse y quedarse corto son el mismo fallo para VD-08, y un
    promedio con signo los dejaria compensarse entre casos hasta dar cero.
    """
    objetivo = (caso or {}).get('palabras_objetivo')
    if not objetivo:
        return None
    return abs(palabras(corrida.get('salida')) - objetivo) / float(objetivo)


def _vd08(corrida, caso, config):
    """El escalon de VD-08: 0 pasa, 1 avisa, 2 bloquea.

    Los dos margenes salen de config.json, como manda §12: aqui no hay ningun
    numero escrito.
    """
    objetivo = (caso or {}).get('palabras_objetivo')
    margenes = (config or {}).get('margenes') or {}
    if not objetivo:
        return None
    texto = corrida.get('salida')
    desvio = abs(palabras(texto) - objetivo) / float(objetivo)
    if desvio > margenes.get('palabras_bloqueo', 0.4):
        return 2
    if parrafos(texto) < margenes.get('parrafos_min', 3):
        return 2
    if desvio > margenes.get('palabras_aviso', 0.15):
        return 1
    return 0


def _vd01(corrida, caso, config):
    """Forma: 1 si la salida no es **solo** el JSON que se le pidio, 0 si lo es.

    Estricta a proposito, y por eso mira el texto y no lo que consiguio rescatar
    `json_de`: el contrato de §5 dice "un unico objeto JSON y nada mas", y un
    rol que antepone un parrafo de cortesia esta gastando tokens en algo que el
    orquestador tira. Solo aplica a los roles que devuelven JSON; para el
    escritor, cuya salida es prosa, el objetivo no debe pedir esta metrica.
    """
    crudo = VALLA.sub('', (corrida.get('salida') or '').strip()).strip()
    if not crudo.startswith('{'):
        return 1
    try:
        json.loads(crudo)
    except ValueError:
        return 1
    return 0


def _datos(corrida, caso, config):
    """Cuantos datos trae el dossier."""
    valor = json_de(corrida.get('salida'))
    if not isinstance(valor, dict):
        return 0
    return len([d for d in (valor.get('datos') or []) if isinstance(d, dict)])


def _categorias(corrida, caso, config):
    """Cuantas de las cuatro categorias utiles cubre el dossier.

    `otro` no cuenta: un dossier entero de `otro` cumpliria el numero sin dar al
    escritor nada de lo que §5 dice que necesita.
    """
    valor = json_de(corrida.get('salida'))
    if not isinstance(valor, dict):
        return 0
    vistas = {d.get('categoria') for d in (valor.get('datos') or [])
              if isinstance(d, dict)}
    return len(vistas & set(CATEGORIAS[:4]))


def _vd04_fallos(corrida, caso, config):
    """VD-04: cuantos datos del dossier estan mal formados.

    Un `verificado` con fuente `modelo` es invalido y por si solo tumba el
    dossier entero en el orquestador; aqui se cuenta para poder exigir cero.
    """
    valor = json_de(corrida.get('salida'))
    if not isinstance(valor, dict):
        return 1
    fallos = 0
    for dato in (valor.get('datos') or []):
        if not isinstance(dato, dict):
            fallos += 1
            continue
        if dato.get('categoria') not in CATEGORIAS:
            fallos += 1
        if dato.get('estado') not in ESTADOS_DATO:
            fallos += 1
        if not str(dato.get('dato') or '').strip():
            fallos += 1
        if (dato.get('estado') == 'verificado'
                and str(dato.get('fuente') or '').strip().lower() == 'modelo'):
            fallos += 1
    return fallos


def _vd10_fallos(corrida, caso, config):
    """VD-10: las tres dimensiones, una vez cada una, con nota entera de 1 a 5."""
    valor = json_de(corrida.get('salida'))
    if not isinstance(valor, dict):
        return 1
    revisiones = valor.get('revisiones')
    if not isinstance(revisiones, list) or len(revisiones) != 3:
        return 1
    fallos = 0
    vistas = []
    for bloque in revisiones:
        if not isinstance(bloque, dict):
            fallos += 1
            continue
        vistas.append(bloque.get('dimension'))
        nota = bloque.get('nota')
        if not (isinstance(nota, int) and not isinstance(nota, bool) and 1 <= nota <= 5):
            fallos += 1
    if sorted(v for v in vistas if v) != sorted(DIMENSIONES):
        fallos += 1
    return fallos


def _media_notas(corrida, caso, config):
    """La media de las tres notas de un validador, para poder vigilarla."""
    valor = json_de(corrida.get('salida'))
    if not isinstance(valor, dict):
        return None
    notas = [b.get('nota') for b in (valor.get('revisiones') or [])
             if isinstance(b, dict) and isinstance(b.get('nota'), int)]
    return sum(notas) / float(len(notas)) if notas else None


MEDIDAS = {
    'tokens_rol': _tokens_rol,
    'tokens_salida': _tokens_salida,
    'tokens_prompt': _tokens_prompt,
    'coste_usd': _coste_usd,
    'segundos': _segundos,
    'palabras': _palabras,
    'parrafos': _parrafos,
    'desvio_palabras': _desvio_palabras,
    'vd08': _vd08,
    'vd01': _vd01,
    'datos': _datos,
    'categorias': _categorias,
    'vd04_fallos': _vd04_fallos,
    'vd10_fallos': _vd10_fallos,
    'media_notas': _media_notas,
}


def medir(corrida, caso, config, nombres=None):
    """Todas las metricas de una corrida, o solo las que se pidan."""
    salida = {}
    for nombre in (nombres or MEDIDAS):
        funcion = MEDIDAS.get(nombre)
        if funcion is None:
            continue
        try:
            salida[nombre] = funcion(corrida, caso, config)
        except Exception:
            # Una metrica que revienta no puede tumbar la ronda: se queda sin
            # numero, que el agregado sabe descartar.
            salida[nombre] = None
    return salida


AGREGADOS = {
    'media': lambda v: sum(v) / float(len(v)),
    'suma': lambda v: sum(v),
    'maximo': max,
    'minimo': min,
}


def agregar(valores, como='media'):
    """Un solo numero para todos los casos. Los None no cuentan.

    Un caso sin numero no es un cero: es un caso que no midio. Contarlo como
    cero haria que un candidato que falla en la mitad de los casos saliera
    baratisimo, que es exactamente al reves de lo que pasa.
    """
    limpios = [v for v in valores if isinstance(v, (int, float))
               and not isinstance(v, bool)]
    if not limpios:
        return None
    return AGREGADOS.get(como, AGREGADOS['media'])(limpios)
