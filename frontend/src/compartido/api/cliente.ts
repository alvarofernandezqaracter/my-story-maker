// Único punto de salida HTTP de la interfaz (SPEC2 RI-01). Una función por
// operación que usa (RI-03 a RI-09 y §4.5 a §4.9), y ninguna más. Los tipos salen del
// contrato generado: una ruta o un campo renombrado rompe al compilar.
import createClient from "openapi-fetch";
import type { paths } from "./esquema";
import { falloDeRed, falloDesde, type Fallo } from "./fallos";
import type { PeticionDeEntrevista, PuertaDePublicacion } from "./tipos";

export const BASE_API = new URL("/api", window.location.origin).href.replace(/\/$/, "");

// El fetch se resuelve en cada llamada, no al cargar el módulo, para que quien
// lo sustituya después (las pruebas con msw) también pase por aquí.
const http = createClient<paths>({
  baseUrl: BASE_API,
  fetch: (peticion) => globalThis.fetch(peticion),
});

export type Resultado<T> = { ok: true; datos: T } | { ok: false; fallo: Fallo };

async function llamar<T>(
  peticion: () => Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<Resultado<T>> {
  try {
    const { data, error, response } = await peticion();
    if (response.ok && data !== undefined) return { ok: true, datos: data };
    return { ok: false, fallo: falloDesde(response.status, error) };
  } catch {
    return { ok: false, fallo: falloDeRed() };
  }
}

const enObra = (id: string) => ({ params: { path: { id_obra: id } } });

export const abrirEntrevista = (cuerpo: PeticionDeEntrevista) =>
  llamar(() => http.POST("/entrevistas", { body: cuerpo }));

export const pasarEntrevista = (id: string, cuerpo: PeticionDeEntrevista) =>
  llamar(() =>
    http.POST("/entrevistas/{id_entrevista}/pasadas", {
      params: { path: { id_entrevista: id } },
      body: cuerpo,
    }),
  );

// Todas las obras con su situación, para el taller (SPEC2 RI-09).
export const listarObras = () => llamar(() => http.GET("/obras"));

export const verObra = (id: string) => llamar(() => http.GET("/obras/{id_obra}", enObra(id)));

export const verProgresoAhora = (id: string) =>
  llamar(() => http.GET("/obras/{id_obra}/progreso/ahora", enObra(id)));

export const verTrazas = (id: string) =>
  llamar(() => http.GET("/obras/{id_obra}/trazas", enObra(id)));

// Sin versión, el servidor sirve la de referencia (SPEC1 RF-117).
const deVersion = (id: string, version?: number) => ({
  params: { path: { id_obra: id }, query: version === undefined ? {} : { version } },
});

export const leerManuscrito = (id: string, version?: number) =>
  llamar(() => http.GET("/obras/{id_obra}/manuscrito", deVersion(id, version)));

export const verHechos = (id: string, version?: number) =>
  llamar(() => http.GET("/obras/{id_obra}/hechos", deVersion(id, version)));

export const verVersiones = (id: string) =>
  llamar(() => http.GET("/obras/{id_obra}/versiones", enObra(id)));

export const verCriticasDelCapitulo = (id: string, capitulo: number, version?: number) =>
  llamar(() =>
    http.GET("/obras/{id_obra}/criticas", {
      params: {
        path: { id_obra: id },
        query: version === undefined ? { capitulo } : { capitulo, version },
      },
    }),
  );

const enVersion = (id: string, numero: number) => ({
  params: { path: { id_obra: id, numero } },
});

export const verPuerta = (id: string, numero: number) =>
  llamar(() => http.GET("/obras/{id_obra}/versiones/{numero}/puerta", enVersion(id, numero)));

export type RechazoDePublicar = { ok: false; fallo: Fallo; puerta: PuertaDePublicacion | null };

function puertaDe(cuerpo: unknown): PuertaDePublicacion | null {
  if (typeof cuerpo !== "object" || cuerpo === null || !("puerta" in cuerpo)) return null;
  const puerta = (cuerpo as { puerta: unknown }).puerta;
  return typeof puerta === "object" && puerta !== null ? (puerta as PuertaDePublicacion) : null;
}

/** Publicar: si la puerta no pasa, el 409 trae su resultado entero (SPEC1 RI-18). */
export async function publicarVersion(id: string, numero: number) {
  try {
    const { data, error, response } = await http.POST(
      "/obras/{id_obra}/versiones/{numero}/publicar",
      enVersion(id, numero),
    );
    if (response.ok && data !== undefined) return { ok: true as const, datos: data };
    const rechazo: RechazoDePublicar = {
      ok: false,
      fallo: falloDesde(response.status, error),
      puerta: puertaDe(error),
    };
    return rechazo;
  } catch {
    const rechazo: RechazoDePublicar = { ok: false, fallo: falloDeRed(), puerta: null };
    return rechazo;
  }
}

export const cambiarHecho = (id: string, hecho: string, valor: string) =>
  llamar(() => http.POST("/obras/{id_obra}/cambios", { ...enObra(id), body: { hecho, valor } }));

/** La descarga la hace el navegador: aquí solo se compone la dirección (SPEC2 RF-77). */
export function enlaceDelPdf(id: string, version?: number): string {
  const consulta = version === undefined ? "" : `?version=${version}`;
  return `${BASE_API}/obras/${encodeURIComponent(id)}/pdf${consulta}`;
}

export const detenerObra = (id: string, motivo: string) =>
  llamar(() => http.POST("/obras/{id_obra}/detener", { ...enObra(id), body: { motivo } }));

export const reanudarObra = (id: string) =>
  llamar(() => http.POST("/obras/{id_obra}/reanudar", enObra(id)));
