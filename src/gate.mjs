// §8 Gate de calidad. Codigo puro: tres notas y sus incidencias entran, una
// decision sale. El gate no sabe si las revisiones vinieron de una llamada al
// validador o de tres (§5), solo que ya pasaron VD-10.
import { DIMENSIONES } from './esquemas.mjs';

export function notas(revisiones) {
  return revisiones.map((r) => r.nota);
}

export function media(valores) {
  if (valores.length === 0) return 0;
  return valores.reduce((a, b) => a + b, 0) / valores.length;
}

export function incidenciasGraves(revisiones) {
  return revisiones.flatMap((r) => (r.incidencias ?? [])
    .filter((i) => i.severidad === 'grave')
    .map((i) => ({ ...i, dimension: r.dimension })));
}

/**
 * aprueba = min(notas) >= nota_minima y media(notas) >= media_minima
 *           y ninguna incidencia grave.
 * La incidencia grave veta por si sola: un capitulo puede sacar tres cuatros y
 * caer por una contradiccion de canon, porque eso no se arregla puntuando mas alto.
 */
export function gate(revisiones, configGate) {
  const ns = notas(revisiones);
  const minima = Math.min(...ns);
  const promedio = media(ns);
  const graves = incidenciasGraves(revisiones);

  const motivos = [];
  if (minima < configGate.nota_minima) {
    motivos.push(`nota minima ${minima} por debajo de ${configGate.nota_minima}`);
  }
  if (promedio < configGate.media_minima) {
    motivos.push(`media ${promedio.toFixed(2)} por debajo de ${configGate.media_minima}`);
  }
  if (graves.length) {
    motivos.push(`${graves.length} incidencia(s) grave(s)`);
  }

  return {
    aprueba: motivos.length === 0,
    minima,
    media: promedio,
    graves,
    motivos,
  };
}

/** Al agotar intentos se conserva el de mejor media, en estado propuesto (§8). */
export function mejorIntento(intentos) {
  const conRevisiones = intentos.filter((i) => Array.isArray(i.revisiones) && i.revisiones.length);
  if (!conRevisiones.length) return intentos.at(-1) ?? null;
  return conRevisiones.reduce((mejor, actual) => (
    media(notas(actual.revisiones)) > media(notas(mejor.revisiones)) ? actual : mejor
  ));
}

/** Las incidencias del intento anterior, ordenadas por severidad (§8). */
export function incidenciasOrdenadas(revisiones) {
  const orden = { grave: 0, aviso: 1 };
  return revisiones
    .flatMap((r) => (r.incidencias ?? []).map((i) => ({ ...i, dimension: r.dimension })))
    .sort((a, b) => (orden[a.severidad] ?? 9) - (orden[b.severidad] ?? 9)
      || DIMENSIONES.indexOf(a.dimension) - DIMENSIONES.indexOf(b.dimension));
}
