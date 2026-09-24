// Leer y escribir JSON en el almacenamiento del navegador. Cada acceso va en
// try/catch: el almacenamiento puede no existir, estar lleno o bloqueado, y
// eso nunca tumba una pantalla.

export type Lectura<T> =
  | { estado: "vacio" }
  | { estado: "leido"; valor: T }
  | { estado: "ilegible" };

export function leer<T>(clave: string, validar: (valor: unknown) => valor is T): Lectura<T> {
  try {
    const texto = window.localStorage.getItem(clave);
    if (texto === null) return { estado: "vacio" };
    const valor: unknown = JSON.parse(texto);
    return validar(valor) ? { estado: "leido", valor } : { estado: "ilegible" };
  } catch {
    return { estado: "ilegible" };
  }
}

/** Devuelve false si no se ha podido guardar. */
export function escribir(clave: string, valor: unknown): boolean {
  try {
    window.localStorage.setItem(clave, JSON.stringify(valor));
    return true;
  } catch {
    return false;
  }
}

export function borrar(clave: string): void {
  try {
    window.localStorage.removeItem(clave);
  } catch {
    // Si no se puede borrar, la próxima lectura lo dirá; no hay nada más que hacer.
  }
}
