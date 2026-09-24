// Unidades -> capítulos -> escenas, respetando el orden en que llegan. Es
// presentación, no dominio: no reordena, no filtra y no decide nada.
import type { UnidadDelManuscrito } from "../../compartido/api/tipos";

export type EscenaLeida = { escena: string; parrafos: string[] };
export type CapituloLeido = { capitulo: number; marcado: boolean; escenas: EscenaLeida[] };

/** Un párrafo por cada bloque separado por líneas en blanco. */
export function parrafos(texto: string): string[] {
  return texto
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p !== "");
}

export function agrupar(unidades: UnidadDelManuscrito[]): CapituloLeido[] {
  const capitulos: CapituloLeido[] = [];
  for (const unidad of unidades) {
    let actual = capitulos.at(-1);
    if (!actual || actual.capitulo !== unidad.capitulo) {
      actual = { capitulo: unidad.capitulo, marcado: false, escenas: [] };
      capitulos.push(actual);
    }
    // Un capítulo va marcado si alguna de sus unidades trae la marca.
    actual.marcado ||= unidad.capitulo_marcado;
    actual.escenas.push({ escena: unidad.escena, parrafos: parrafos(unidad.texto) });
  }
  return capitulos;
}
