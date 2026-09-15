// Modo de ejecucion real (§12): las llamadas van a la API de Claude con el
// SDK oficial. El SDK se importa de forma perezosa para que el modo simulado,
// que es el de por defecto, no necesite ninguna dependencia instalada.
//
// §13: ante un error del proveedor se reintenta la llamada una vez; si vuelve a
// fallar, el proceso para y deja el estado escrito. No hay backoff ni politica
// de reintentos finos, y es deliberado.

const MAX_TOKENS = 32000;

let clientePrometido = null;

async function cliente() {
  if (!clientePrometido) {
    clientePrometido = import('@anthropic-ai/sdk')
      .then((m) => new m.default())
      .catch((e) => {
        throw new Error(
          'el modo real necesita el SDK oficial: npm install @anthropic-ai/sdk'
          + ` (${e.message})`,
        );
      });
  }
  return clientePrometido;
}

/**
 * El contrato de salida se pide en el prompt y lo verifica VD-01 al recibirlo.
 * Si el modelo devuelve algo que no parsea, el harness reintenta la llamada una
 * vez y para: ese camino ya esta previsto en §9.
 */
function instruccionDeFormato(rol) {
  return [
    '',
    '# Formato de salida',
    '',
    `Responde unica y exclusivamente con un objeto JSON valido para el rol ${rol},`,
    'sin texto antes ni despues y sin vallas de codigo. El harness lo parsea tal cual.',
  ].join('\n');
}

/** Extrae el primer objeto JSON del texto, tolerando vallas de codigo. */
export function extraerJson(texto) {
  const limpio = String(texto).trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/```$/, '')
    .trim();
  try {
    return JSON.parse(limpio);
  } catch {
    const inicio = limpio.indexOf('{');
    const fin = limpio.lastIndexOf('}');
    if (inicio === -1 || fin <= inicio) {
      throw new SyntaxError('la respuesta del modelo no contiene un objeto JSON');
    }
    return JSON.parse(limpio.slice(inicio, fin + 1));
  }
}

export async function llamarAlProveedor({ rol, modelo, instrucciones, entrada }) {
  const anthropic = await cliente();
  const stream = anthropic.messages.stream({
    model: modelo,
    max_tokens: MAX_TOKENS,
    system: instrucciones + instruccionDeFormato(rol),
    thinking: { type: 'adaptive' },
    output_config: { effort: 'high' },
    messages: [{ role: 'user', content: JSON.stringify(entrada, null, 2) }],
  });
  const mensaje = await stream.finalMessage();

  if (mensaje.stop_reason === 'refusal') {
    throw new Error(`el modelo declino la peticion del rol ${rol}`
      + `: ${mensaje.stop_details?.category ?? 'sin categoria'}`);
  }

  const texto = mensaje.content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('');

  return { salida: extraerJson(texto), uso: mensaje.usage };
}
