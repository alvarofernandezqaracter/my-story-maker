// El backend simulado con msw: ninguna prueba gasta un subagente de verdad.
// Las respuestas llevan los tipos del contrato, así que si el borde cambia
// estas muestras dejan de compilar.
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type {
  Confirmacion,
  FichaDeObra,
  Manuscrito,
  PasadaDeEntrevista,
  Progreso,
  TrazaServida,
} from "../src/compartido/api/tipos";

export const API = "http://localhost:5173/api";
export const ID_OBRA = "obra-1";

export function ficha(cambios: Partial<FichaDeObra> = {}): FichaDeObra {
  return {
    id_obra: ID_OBRA,
    titulo: "La luz de Triana",
    detenida: false,
    capitulo_en_curso: 2,
    capitulos_cerrados: 1,
    capitulos_marcados: 1,
    criticas_abiertas: 3,
    version_en_curso: 1,
    version_publicada: null,
    ...cambios,
  };
}

export function progreso(cambios: Partial<Progreso> = {}): Progreso {
  return {
    id_obra: ID_OBRA,
    detenida: false,
    capitulo_en_curso: 2,
    tareas_abiertas: [
      { rol: "redactor", tarea: "redactar_escena", capitulo: 2, escena: "e2", tokens: 3100 },
    ],
    tokens_de_entrada_concurrentes: 12340,
    techo: 100000,
    ...cambios,
  };
}

export function manuscrito(cambios: Partial<Manuscrito> = {}): Manuscrito {
  return {
    id_obra: ID_OBRA,
    version: 1,
    publicada: false,
    unidades: [
      { capitulo: 1, escena: "e1", texto: "Amanecía sobre el río.\n\nLa barca esperaba.", capitulo_marcado: false },
      { capitulo: 1, escena: "e2", texto: "El mercado ya hervía.", capitulo_marcado: false },
      { capitulo: 2, escena: "e1", texto: "La carta llegó de noche.", capitulo_marcado: true },
    ],
    ...cambios,
  };
}

export function pasada(cambios: Partial<PasadaDeEntrevista> = {}): PasadaDeEntrevista {
  return {
    id_entrevista: "ent-1",
    numero: 1,
    estado: "pendiente",
    id_obra: null,
    brief_propuesto: {},
    faltan: [],
    no_validos: [],
    hechos: [],
    hechos_descartados: [],
    contradicciones: [],
    contradicciones_descartadas: 0,
    ...cambios,
  };
}

export function traza(cambios: Partial<TrazaServida> = {}): TrazaServida {
  return {
    id: "tra-1",
    capitulo: 1,
    escena: "e1",
    rol: "redactor",
    tarea: "redactar_escena",
    intento: 1,
    tokens_de_entrada_estimados: 3000,
    tokens_de_entrada_medidos: 3100,
    tokens_de_salida: 900,
    coste: 0.01,
    latencia_ms: 42000,
    abierta_en: "2026-09-24T10:00:00Z",
    cerrada_en: "2026-09-24T10:00:42Z",
    ganchos: null,
    ...cambios,
  };
}

export const confirmacion = (detenida: boolean, motivo: string | null = null): Confirmacion => ({
  id_obra: ID_OBRA,
  detenida,
  motivo,
});

export const servidor = setupServer(
  http.get(`${API}/obras/:id`, () => HttpResponse.json(ficha())),
  http.get(`${API}/obras/:id/progreso/ahora`, () => HttpResponse.json(progreso())),
  http.get(`${API}/obras/:id/manuscrito`, () => HttpResponse.json(manuscrito())),
  http.get(`${API}/obras/:id/trazas`, () => HttpResponse.json([traza()])),
);

/** Lo que devuelve el proxy de Vite cuando no alcanza el backend: 500 sin JSON. */
export const sinServidor = () => new HttpResponse(null, { status: 500 });
