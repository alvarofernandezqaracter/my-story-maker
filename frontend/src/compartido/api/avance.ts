// El único sitio que sabe que el avance llega por un flujo empujado por el
// servidor (SPEC2 RNF-04). Pasarlo a sondeo es reescribir este fichero y nada
// más: las pantallas solo ven los tres oyentes.
import { BASE_API } from "./cliente";
import type { paths } from "./esquema";
import type { Progreso } from "./tipos";

export type EstadoDelFlujo = "conectando" | "en_directo" | "reconectando";

export type Oyentes = {
  alProgreso: (progreso: Progreso) => void;
  /** Llegó `terminada`: el flujo ya está cerrado y no se reabre. */
  alTerminar: () => void;
  alEstado: (estado: EstadoDelFlujo, intentos: number) => void;
};

// La ruta se comprueba contra el contrato: si el backend la mueve, rompe aquí.
const RUTA_DEL_FLUJO = "/obras/{id_obra}/progreso" satisfies keyof paths;

// Esperas entre reintentos, en segundos; la última se repite indefinidamente.
const ESPERAS = [1, 2, 4, 8, 15];

export function seguirElAvance(
  idObra: string,
  oyentes: Oyentes,
  fabrica: (url: string) => EventSource = (url) => new EventSource(url),
): () => void {
  const url = BASE_API + RUTA_DEL_FLUJO.replace("{id_obra}", encodeURIComponent(idObra));
  let fuente: EventSource | null = null;
  let temporizador: ReturnType<typeof setTimeout> | null = null;
  let intentos = 0;
  let apagado = false;

  function cerrar() {
    fuente?.close();
    fuente = null;
  }

  function abrir() {
    if (apagado) return;
    oyentes.alEstado(intentos === 0 ? "conectando" : "reconectando", intentos);
    const nueva = fabrica(url);
    fuente = nueva;
    nueva.addEventListener("open", () => {
      intentos = 0;
      oyentes.alEstado("en_directo", 0);
    });
    nueva.addEventListener("progreso", (evento) => {
      oyentes.alProgreso(JSON.parse((evento as MessageEvent<string>).data) as Progreso);
    });
    nueva.addEventListener("terminada", () => {
      // Hay que cerrar: si no, el navegador reconecta solo y vuelve a empezar.
      apagado = true;
      cerrar();
      oyentes.alTerminar();
    });
    nueva.addEventListener("error", () => {
      if (apagado) return;
      // El reenganche es propio: el del navegador no se reintenta tras una
      // respuesta de error y no dice cuántas veces lleva.
      cerrar();
      intentos += 1;
      oyentes.alEstado("reconectando", intentos);
      const espera = ESPERAS[Math.min(intentos, ESPERAS.length) - 1] ?? 15;
      temporizador = setTimeout(abrir, espera * 1000);
    });
  }

  abrir();

  return () => {
    apagado = true;
    if (temporizador !== null) clearTimeout(temporizador);
    cerrar();
  };
}
