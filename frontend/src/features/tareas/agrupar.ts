// Trazas -> grupos por capítulo, en el orden en que llegan, y lo que se pinta de
// cada una. Es presentación: no reordena, no cuenta tokens y no juzga nada.
import type { TrazaServida } from "../../compartido/api/tipos";

export type GrupoDeTareas = { capitulo: number | null; tareas: TrazaServida[] };

export function agruparPorCapitulo(trazas: TrazaServida[]): GrupoDeTareas[] {
  const grupos: GrupoDeTareas[] = [];
  for (const traza of trazas) {
    let actual = grupos.at(-1);
    if (!actual || actual.capitulo !== traza.capitulo) {
      actual = { capitulo: traza.capitulo, tareas: [] };
      grupos.push(actual);
    }
    actual.tareas.push(traza);
  }
  return grupos;
}

/** «verificador_de_continuidad» -> «Verificador de continuidad». Solo cambia cómo se lee. */
export function legible(nombre: string | null): string {
  if (!nombre) return "—";
  const texto = nombre.replace(/_/g, " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** La suma de las latencias que manda el servidor, para el resumen de arriba. */
export function tiempoTotal(trazas: TrazaServida[]): string {
  const minutos = Math.round(trazas.reduce((s, t) => s + (t.latencia_ms ?? 0), 0) / 60000);
  if (minutos < 60) return `${minutos} min`;
  return `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}

/** La latencia que manda el servidor, en segundos redondeados para leerla. */
export function duracion(traza: TrazaServida): string {
  if (traza.cerrada_en === null) return "En curso";
  if (traza.latencia_ms === null) return "—";
  const segundos = Math.round(traza.latencia_ms / 1000);
  return segundos < 60 ? `${segundos} s` : `${Math.floor(segundos / 60)} min ${segundos % 60} s`;
}
