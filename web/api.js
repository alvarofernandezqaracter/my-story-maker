// Capa fina sobre la API del harness (§19). Aqui no hay reglas del sistema:
// solo fetch, JSON y un error con su codigo para que quien llame decida.

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
    throw new ErrorApi(0, 'no se puede hablar con el harness: ¿sigue corriendo "novela ui"?');
  }
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, datos.error || 'el harness ha devuelto un error');
  }
  return datos;
}

const enviar = (camino, cuerpo) => pedir(camino, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(cuerpo),
});

export const api = {
  proyecto: () => pedir('/api/proyecto'),
  guardarBrief: (brief) => enviar('/api/brief', brief),
  flujo: (desde = 0) => pedir(`/api/flujo?desde=${desde}`),
  arrancar: (accion, perfil) => enviar('/api/flujo', { accion, perfil }),
  capitulo: (numero) => pedir(`/api/capitulo/${numero}`),
  desbloquear: (datos) => enviar('/api/desbloquear', datos),
};

export { ErrorApi };
