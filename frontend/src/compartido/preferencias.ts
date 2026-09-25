// Preferencias de la propia interfaz —tema, tamaño de letra, dónde se quedó el
// lector—. No son dominio: si se pierden, la pantalla sale con sus valores de
// siempre. Todo pasa por almacen-local.
import { useState } from "react";
import { escribir, leer } from "./almacen-local";

const PREFIJO = "msm:preferencia:";

export function leerPreferencia<T>(clave: string, porDefecto: T, validar: (v: unknown) => v is T): T {
  const lectura = leer(PREFIJO + clave, validar);
  return lectura.estado === "leido" ? lectura.valor : porDefecto;
}

export function usePreferencia<T>(
  clave: string,
  porDefecto: T,
  validar: (v: unknown) => v is T,
): [T, (valor: T) => void] {
  const [valor, setValor] = useState<T>(() => leerPreferencia(clave, porDefecto, validar));
  function cambiar(nuevo: T) {
    setValor(nuevo);
    escribir(PREFIJO + clave, nuevo);
  }
  return [valor, cambiar];
}

export const esUnoDe =
  <T extends string>(valores: readonly T[]) =>
  (v: unknown): v is T =>
    typeof v === "string" && (valores as readonly string[]).includes(v);

export const esNumeroEntre =
  (minimo: number, maximo: number) =>
  (v: unknown): v is number =>
    typeof v === "number" && Number.isFinite(v) && v >= minimo && v <= maximo;

// --- El tema de toda la interfaz ------------------------------------------

export const TEMAS = ["sistema", "claro", "oscuro"] as const;
export type Tema = (typeof TEMAS)[number];

export function aplicarTema(tema: Tema): void {
  const raiz = document.documentElement;
  if (tema === "sistema") delete raiz.dataset.tema;
  else raiz.dataset.tema = tema;
}

export function temaGuardado(): Tema {
  return leerPreferencia<Tema>("tema", "sistema", esUnoDe(TEMAS));
}

/** Guarda sin estado de React, para lo que se escribe a menudo (dónde va el lector). */
export function guardarPreferencia(clave: string, valor: unknown): void {
  escribir(PREFIJO + clave, valor);
}

/** Si la interfaz se está viendo en oscuro, por elección o por el sistema. */
export function seVeOscuro(): boolean {
  const elegido = document.documentElement.dataset.tema;
  if (elegido === "oscuro") return true;
  if (elegido === "claro") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}
