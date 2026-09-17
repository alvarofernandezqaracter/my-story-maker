// Capa fina sobre la API de §19. Aqui no hay reglas del sistema: solo fetch,
// JSON y un error con su codigo para que quien llame decida.
//
// Lo unico que anade es el camino (§1): todas las lecturas llevan pegado por
// cual de los dos canones se pregunta, y la primera va sin el a proposito para
// que conteste el perfil (§12).

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

const enviar = (camino, cuerpo) => pedir(camino, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: cuerpo === undefined ? '' : JSON.stringify(cuerpo),
});

// `via` a null significa "el que diga el perfil": es como arranca la pagina.
const con = (ruta, via) => (via ? `${ruta}${ruta.includes('?') ? '&' : '?'}camino=${via}` : ruta);

export const api = {
  proyecto: (via) => pedir(con('/api/proyecto', via)),
  guardarBrief: (brief, via) => enviar(con('/api/brief', via), brief),
  flujo: (desde = 0, via) => pedir(con(`/api/flujo?desde=${desde}`, via)),
  arrancar: (accion, perfil, via) => enviar(con('/api/flujo', via), { accion, perfil }),
  capitulo: (numero, via) => pedir(con(`/api/capitulo/${numero}`, via)),
  contexto: (numero, via) => pedir(con(`/api/contexto/${numero}`, via)),
  desbloquear: (datos, via) => enviar(con('/api/desbloquear', via), datos),
  trazas: (via) => pedir(con('/api/trazas', via)),
  exportarTrazas: (via) => enviar(con('/api/trazas', via)),
};

export { ErrorApi };
