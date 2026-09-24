// Etiqueta legible de cada ruta del brief y de cada tipo de contradicción.
// Es presentación: no decide qué falta ni qué choca, solo cómo se llama.
import type { TipoDeContradiccion } from "../../compartido/api/tipos";

export type ClaseDeCampo = "texto" | "largo" | "numero" | "lista";

export type Campo = {
  ruta: string;
  etiqueta: string;
  clase: ClaseDeCampo;
  ayuda?: string;
  /** Se puede dejar sin tocar: el servidor no lo exige (SPEC1 RF-01, D-50). */
  opcional?: boolean;
};

export const GRUPOS: { titulo: string; nota?: string; campos: Campo[] }[] = [
  {
    titulo: "La obra",
    campos: [
      { ruta: "titulo", etiqueta: "Título", clase: "texto" },
      { ruta: "epoca", etiqueta: "Época y lugar", clase: "texto", ayuda: "Por ejemplo: Sevilla, 1587" },
      { ruta: "premisa", etiqueta: "De qué va", clase: "largo" },
      { ruta: "tesis_tematica", etiqueta: "Qué sostiene la obra", clase: "largo", opcional: true },
      {
        ruta: "elenco_declarado",
        etiqueta: "Personajes que fijas",
        clase: "lista",
        opcional: true,
        ayuda: "Si lo dejas vacío, los decide el sistema",
      },
      { ruta: "capitulos_objetivo", etiqueta: "Cuántos capítulos", clase: "numero" },
      {
        ruta: "arcos",
        etiqueta: "Arcos",
        clase: "lista",
        opcional: true,
        ayuda: "Cómo cambia un personaje de principio a fin, uno por línea",
      },
    ],
  },
  {
    titulo: "El destinatario (opcional)",
    nota: "Si rellenas alguno, el nombre, la edad, el tono y la dedicatoria pasan a ser obligatorios.",
    campos: [
      { ruta: "destinatario.nombre", etiqueta: "Nombre", clase: "texto" },
      { ruta: "destinatario.edad", etiqueta: "Edad", clase: "numero" },
      { ruta: "destinatario.tono", etiqueta: "Tono", clase: "texto" },
      { ruta: "destinatario.dedicatoria", etiqueta: "Dedicatoria", clase: "largo" },
      { ruta: "destinatario.rasgos", etiqueta: "Cómo es", clase: "lista", opcional: true },
      { ruta: "destinatario.recuerdos", etiqueta: "Recuerdos", clase: "lista", opcional: true },
      {
        ruta: "destinatario.vetos",
        etiqueta: "Palabras o temas vetados",
        clase: "lista",
        opcional: true,
      },
    ],
  },
];

export const CAMPOS: Campo[] = GRUPOS.flatMap((grupo) => grupo.campos);

const POR_RUTA = new Map(CAMPOS.map((campo) => [campo.ruta, campo]));

export function campoDe(ruta: string): Campo | undefined {
  return POR_RUTA.get(ruta);
}

/** La etiqueta de una ruta; si la ruta no está en la ficha, la ruta tal cual. */
export function etiquetaDe(ruta: string): string {
  return POR_RUTA.get(ruta)?.etiqueta ?? ruta;
}

// Uno a uno, sin juntar dos valores en uno (SPEC2 RD-03). Al ser un Record
// exhaustivo, un tipo nuevo en el contrato obliga a darle su etiqueta.
export const ETIQUETA_DE_CONTRADICCION: Record<TipoDeContradiccion, string> = {
  edad_contra_tono: "La edad no casa con el tono",
  texto_contra_campo: "Un texto pegado dice otra cosa que un campo",
};
