// Capa fina sobre la API de §19. Aqui no hay reglas del sistema: solo fetch,
// JSON y un error con su codigo para que quien llame decida.
//
// Todas las rutas son lecturas menos dos, y ninguna de las dos toca el canon.
// En el canon escribe la sesion de Claude Code que orquesta (§21):
// `exportarTrazas` manda a Langfuse lo que el canon ya dice, y `lanzar` arranca
// esa sesion con un brief delante y se aparta.

class ErrorApi extends Error {
  constructor(codigo, mensaje) {
    super(mensaje);
    this.codigo = codigo;
  }
}

async function pedir(camino, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(camino, opciones);
  } catch {
    throw new ErrorApi(0, 'no se puede hablar con el servidor: ¿sigue corriendo "novela ui"?');
  }
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, datos.error || 'el servidor ha devuelto un error');
  }
  return datos;
}

// La novela que se esta mirando. Sin ella, el servidor da la novela en curso,
// que es la que se toco ultima (§21); con ella, cualquier carpeta de biblioteca/.
let novela = null;

function conNovela(camino) {
  return novela ? `${camino}?novela=${encodeURIComponent(novela)}` : camino;
}

export const api = {
  get novela() { return novela; },
  set novela(nombre) { novela = nombre || null; },
  novelas: () => pedir('/api/novelas'),
  proyecto: () => pedir(conNovela('/api/proyecto')),
  capitulo: (numero) => pedir(conNovela(`/api/capitulo/${numero}`)),
  contexto: (numero) => pedir(conNovela(`/api/contexto/${numero}`)),
  trazas: () => pedir(conNovela('/api/trazas')),
  exportarTrazas: () => pedir(conNovela('/api/trazas'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '',
  }),
  lanzamiento: () => pedir('/api/lanzar'),
  lanzar: (brief) => pedir('/api/lanzar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brief),
  }),
};

export { ErrorApi };
