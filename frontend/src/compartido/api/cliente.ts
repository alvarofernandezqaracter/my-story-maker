// Único punto de salida HTTP de la interfaz (SPEC2 RI-01). Una función por
// operación que usa v1 (RI-03 a RI-08), y ninguna más. Los tipos salen del
// contrato generado: una ruta o un campo renombrado rompe al compilar.
import createClient from "openapi-fetch";
import type { paths } from "./esquema";
import { falloDeRed, falloDesde, type Fallo } from "./fallos";
import type { PeticionDeEntrevista } from "./tipos";

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

export const verObra = (id: string) => llamar(() => http.GET("/obras/{id_obra}", enObra(id)));

export const verProgresoAhora = (id: string) =>
  llamar(() => http.GET("/obras/{id_obra}/progreso/ahora", enObra(id)));

export const verTrazas = (id: string) =>
  llamar(() => http.GET("/obras/{id_obra}/trazas", enObra(id)));

export const leerManuscrito = (id: string) =>
  llamar(() => http.GET("/obras/{id_obra}/manuscrito", enObra(id)));

export const detenerObra = (id: string, motivo: string) =>
  llamar(() => http.POST("/obras/{id_obra}/detener", { ...enObra(id), body: { motivo } }));

export const reanudarObra = (id: string) =>
  llamar(() => http.POST("/obras/{id_obra}/reanudar", enObra(id)));
