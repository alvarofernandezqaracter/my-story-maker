// Un EventSource que la prueba maneja a mano: abrir, mandar sucesos con nombre,
// cortar. Cada instancia creada queda en `EventSourceFalso.creadas`.
import type { Progreso } from "../src/compartido/api/tipos";

export class EventSourceFalso extends EventTarget {
  static creadas: EventSourceFalso[] = [];

  static reiniciar() {
    EventSourceFalso.creadas = [];
  }

  static ultima(): EventSourceFalso {
    const ultima = EventSourceFalso.creadas.at(-1);
    if (!ultima) throw new Error("No se ha abierto ningún EventSource");
    return ultima;
  }

  readonly url: string;
  cerrada = false;

  constructor(url: string) {
    super();
    this.url = url;
    EventSourceFalso.creadas.push(this);
  }

  close() {
    this.cerrada = true;
  }

  abrir() {
    this.dispatchEvent(new Event("open"));
  }

  progreso(progreso: Progreso) {
    this.dispatchEvent(new MessageEvent("progreso", { data: JSON.stringify(progreso) }));
  }

  terminada() {
    this.dispatchEvent(new MessageEvent("terminada", { data: "{}" }));
  }

  cortar() {
    this.dispatchEvent(new Event("error"));
  }
}
