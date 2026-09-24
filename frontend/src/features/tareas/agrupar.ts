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

export type Veredicto = "pasa" | "no_pasa" | "sin_hooks";

type Final = { pasa?: unknown };

// Se lee del veredicto `final` que ya trae la Traza (SPEC2 RF-27, SPEC1 RI-15):
// pasa si todos los hooks dicen que pasa. Sin hooks, no se dice nada.
export function veredictoDeLosHooks(traza: TrazaServida): Veredicto {
  const final = traza.ganchos?.final;
  if (!Array.isArray(final) || final.length === 0) return "sin_hooks";
  return (final as Final[]).every((f) => f.pasa === true) ? "pasa" : "no_pasa";
}

/** La latencia que manda el servidor, en segundos redondeados para leerla. */
export function duracion(traza: TrazaServida): string {
  if (traza.cerrada_en === null) return "En curso";
  if (traza.latencia_ms === null) return "—";
  const segundos = Math.round(traza.latencia_ms / 1000);
  return segundos < 60 ? `${segundos} s` : `${Math.floor(segundos / 60)} min ${segundos % 60} s`;
}
