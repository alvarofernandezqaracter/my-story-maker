// Ayudas de presentación para leer: números romanos, cuánto se tarda en leer y
// la búsqueda dentro del texto. No deciden nada del dominio.
import type { CapituloLeido } from "./agrupar";

const ROMANOS: [number, string][] = [
  [1000, "M"],
  [900, "CM"],
  [500, "D"],
  [400, "CD"],
  [100, "C"],
  [90, "XC"],
  [50, "L"],
  [40, "XL"],
  [10, "X"],
  [9, "IX"],
  [5, "V"],
  [4, "IV"],
  [1, "I"],
];

export function romano(numero: number): string {
  if (!Number.isInteger(numero) || numero <= 0) return String(numero);
  let resto = numero;
  let texto = "";
  for (const [valor, letra] of ROMANOS) {
    while (resto >= valor) {
      texto += letra;
      resto -= valor;
    }
  }
  return texto;
}

const PALABRAS_POR_MINUTO = 230;

export function palabrasDe(capitulo: CapituloLeido): number {
  let total = 0;
  for (const escena of capitulo.escenas) {
    for (const parrafo of escena.parrafos) total += parrafo.split(/\s+/).filter(Boolean).length;
  }
  return total;
}

export function minutosDeLectura(palabras: number): number {
  return Math.max(1, Math.round(palabras / PALABRAS_POR_MINUTO));
}

export function duracion(minutos: number): string {
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  return resto === 0 ? `${horas} h` : `${horas} h ${resto} min`;
}

const formatoDeMiles = new Intl.NumberFormat("es-ES");
export const miles = (n: number) => formatoDeMiles.format(n);

// La búsqueda no distingue mayúsculas ni tildes: «leccion» encuentra «lección».
const VARIANTES: Record<string, string> = {
  a: "aáàäâ",
  e: "eéèëê",
  i: "iíìïî",
  o: "oóòöô",
  u: "uúùüû",
  n: "nñ",
  c: "cç",
};

function sinTildes(letra: string): string {
  return letra.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export function patronDeBusqueda(consulta: string): RegExp | null {
  const limpia = consulta.trim();
  if (limpia.length < 2) return null;
  let fuente = "";
  for (const letra of limpia.toLowerCase()) {
    const base = sinTildes(letra);
    const variantes = VARIANTES[base];
    if (variantes) fuente += `[${variantes}${variantes.toUpperCase()}]`;
    else fuente += letra.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
  return new RegExp(fuente, "gi");
}

export type Trozo = { texto: string; coincide: boolean };

export function trocear(texto: string, patron: RegExp | null): Trozo[] {
  if (patron === null) return [{ texto, coincide: false }];
  const trozos: Trozo[] = [];
  let desde = 0;
  patron.lastIndex = 0;
  for (const encontrado of texto.matchAll(patron)) {
    const inicio = encontrado.index;
    if (inicio > desde) trozos.push({ texto: texto.slice(desde, inicio), coincide: false });
    trozos.push({ texto: encontrado[0], coincide: true });
    desde = inicio + encontrado[0].length;
  }
  if (desde < texto.length) trozos.push({ texto: texto.slice(desde), coincide: false });
  return trozos.length ? trozos : [{ texto, coincide: false }];
}

export function contarCoincidencias(capitulos: CapituloLeido[], patron: RegExp | null): number {
  if (patron === null) return 0;
  let total = 0;
  for (const capitulo of capitulos) {
    for (const escena of capitulo.escenas) {
      for (const parrafo of escena.parrafos) total += parrafo.match(patron)?.length ?? 0;
    }
  }
  return total;
}
