// Borrador + textos + asumidas -> PeticionDeEntrevista (SPEC2 RF-02). Función
// pura. Las reglas de limpieza son de forma, ninguna de dominio.
import type {
  BorradorDeBrief,
  BorradorDeDestinatario,
  PeticionDeEntrevista,
  TipoDeContradiccion,
} from "../../compartido/api/tipos";
import { CAMPOS } from "./campos";

export type Aportacion = { id: string; clase: "mensaje" | "pegado"; texto: string };

export type Encargo = {
  /** Lo que la persona ha escrito en la ficha, por ruta, tal como lo escribió. */
  valores: Record<string, string>;
  /** Rutas de lista que la persona ha tocado: una lista tocada va aunque quede vacía. */
  camposTocados: string[];
  aportaciones: Aportacion[];
  asumidas: TipoDeContradiccion[];
};

/** Una línea por elemento; las líneas en blanco no cuentan. */
export function elementosDeLista(texto: string): string[] {
  return texto
    .split("\n")
    .map((linea) => linea.trim())
    .filter((linea) => linea !== "");
}

function valorDeCampo(encargo: Encargo, ruta: string, clase: string): unknown {
  const texto = encargo.valores[ruta] ?? "";
  if (clase === "lista") {
    return encargo.camposTocados.includes(ruta) ? elementosDeLista(texto) : undefined;
  }
  const limpio = texto.trim();
  if (limpio === "") return undefined;
  if (clase === "numero") {
    const numero = Number(limpio);
    return Number.isFinite(numero) ? numero : undefined;
  }
  return limpio;
}

export function construirPeticion(encargo: Encargo): PeticionDeEntrevista {
  const borrador: Record<string, unknown> = {};
  const destinatario: Record<string, unknown> = {};
  for (const campo of CAMPOS) {
    const valor = valorDeCampo(encargo, campo.ruta, campo.clase);
    if (valor === undefined) continue;
    if (campo.ruta.startsWith("destinatario.")) {
      destinatario[campo.ruta.slice("destinatario.".length)] = valor;
    } else {
      borrador[campo.ruta] = valor;
    }
  }
  if (Object.keys(destinatario).length > 0) {
    borrador.destinatario = destinatario as BorradorDeDestinatario;
  }
  return {
    borrador: borrador as BorradorDeBrief,
    textos: encargo.aportaciones.map((a) => a.texto).filter((t) => t.trim() !== ""),
    contradicciones_asumidas: [...encargo.asumidas],
  };
}

/** El valor de una ruta con puntos dentro de un objeto cualquiera, o undefined. */
export function valorEnRuta(objeto: unknown, ruta: string): unknown {
  let actual: unknown = objeto;
  for (const tramo of ruta.split(".")) {
    if (typeof actual !== "object" || actual === null || Array.isArray(actual)) return undefined;
    actual = (actual as Record<string, unknown>)[tramo];
  }
  return actual;
}
