// El backend simulado con msw: ninguna prueba gasta un subagente de verdad.
// Las respuestas llevan los tipos del contrato, así que si el borde cambia
// estas muestras dejan de compilar.
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type {
  Confirmacion,
  CriticaServida,
  FichaDeObra,
  HechoDeLaBiblia,
  Manuscrito,
  PasadaDeEntrevista,
  Progreso,
  PuertaDePublicacion,
  TrazaServida,
  VersionDeLaObra,
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
    destinatario: "Lucía",
    dedicatoria: "Para Lucía, que me enseñó a leer",
    ...cambios,
  };
}

export function hecho(cambios: Partial<HechoDeLaBiblia> = {}): HechoDeLaBiblia {
  return { id: "per_1", tipo: "Personaje", nombre: "Inés de Salcedo", licencia: "plausible", capitulos: [1, 2], ...cambios };
}

export const hechos = (): HechoDeLaBiblia[] => [
  hecho(),
  hecho({ id: "per_2", nombre: "Nala", licencia: "personal", capitulos: [2] }),
  hecho({ id: "lug_1", tipo: "Lugar", nombre: "Triana", licencia: "canon", capitulos: [] }),
];

export function version(cambios: Partial<VersionDeLaObra> = {}): VersionDeLaObra {
  return {
    numero: 1,
    base: null,
    capitulos_cambiados: [],
    creada_en: "2026-09-24T10:00:00Z",
    terminada_en: "2026-09-24T12:00:00Z",
    terminada: true,
    publicada: false,
    cambio: null,
    ...cambios,
  };
}

export function critica(cambios: Partial<CriticaServida> = {}): CriticaServida {
  return {
    id: "cri_1",
    capitulo: 2,
    escena: "e1",
    estado: "abierta",
    severidad: "bloqueante",
    dimension: "coherencia_temporal",
    detectada_por: "verificador_de_continuidad",
    evidencia: "«llegó antes de salir»",
    accion_sugerida: "Retrasar la llegada",
    ...cambios,
  };
}

export function puerta(cambios: Partial<PuertaDePublicacion> = {}): PuertaDePublicacion {
  return { id_obra: ID_OBRA, version: 1, terminada: true, pasa: true, fallos: [], ...cambios };
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
  http.get(`${API}/obras/:id/hechos`, () => HttpResponse.json(hechos())),
  http.get(`${API}/obras/:id/versiones`, () => HttpResponse.json([version()])),
  http.get(`${API}/obras/:id/criticas`, () => HttpResponse.json([critica()])),
);

/** Lo que devuelve el proxy de Vite cuando no alcanza el backend: 500 sin JSON. */
export const sinServidor = () => new HttpResponse(null, { status: 500 });
