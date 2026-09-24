import type { SituacionDeLaObra } from "./api/tipos";

// La situación de una obra la decide el servidor (SPEC1 RF-205, D-89); aquí solo
// se le pone nombre legible (SPEC2 RD-03). El `Record` sobre el tipo generado hace
// que un valor nuevo del contrato no compile hasta que tenga su etiqueta.
export const ETIQUETA_DE_SITUACION: Record<SituacionDeLaObra, string> = {
  en_produccion: "En producción",
  detenida: "Detenida",
  terminada: "Terminada",
  publicada: "Publicada",
};

// El orden de las columnas del taller (SPEC2 RF-80).
export const ORDEN_DE_SITUACIONES: SituacionDeLaObra[] = [
  "en_produccion",
  "detenida",
  "terminada",
  "publicada",
];
