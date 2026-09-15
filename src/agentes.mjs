// §5 Agentes y §12 modo de ejecucion. Toda llamada a un agente pasa por aqui,
// asi que el resto del harness no sabe si esta corriendo contra la API o contra
// la capa simulada. Ningun agente escribe en el canon: devuelven una propuesta
// que el harness valida (§9) y persiste.
import { AGENTES_SIMULADOS } from './simulado.mjs';
import { llamarAlProveedor } from './proveedor.mjs';
import { instruccionesDe } from './skills.mjs';
import { comprobarSalidaDeAgente } from './validadores.mjs';

/** El proceso para y deja el estado escrito, en vez de insistir (§9, §13). */
export class ParadaDelProceso extends Error {
  constructor(mensaje, detalles = []) {
    super(mensaje);
    this.name = 'ParadaDelProceso';
    this.detalles = detalles;
  }
}

export class Agentes {
  constructor(config, opciones = {}) {
    this.config = config;
    this.raices = opciones;
    this.registro = [];
  }

  get modo() { return this.config.ejecucion.modo; }

  modeloDe(rol) { return this.config.modelo_por_rol[rol]; }

  /** Una llamada cruda, sin validar. Reintenta una vez ante error de proveedor. */
  async #llamar(rol, entrada) {
    if (this.modo === 'simulado') {
      const fn = AGENTES_SIMULADOS[rol];
      if (!fn) throw new Error(`rol sin agente simulado: ${rol}`);
      return fn(entrada);
    }

    const instrucciones = instruccionesDe(rol, this.raices).texto;
    const modelo = this.modeloDe(rol);
    try {
      const { salida } = await llamarAlProveedor({ rol, modelo, instrucciones, entrada });
      return salida;
    } catch (primera) {
      try {
        const { salida } = await llamarAlProveedor({ rol, modelo, instrucciones, entrada });
        return salida;
      } catch (segunda) {
        throw new ParadaDelProceso(
          `el proveedor fallo dos veces en el rol ${rol}`,
          [primera.message, segunda.message],
        );
      }
    }
  }

  /**
   * Llamada con las comprobaciones de forma de §9 (VD-01 y VD-02) y las extra
   * que pase quien llama. Un bloqueante que falla dos veces seguidas sobre el
   * mismo artefacto para el proceso: no hay reintento infinito.
   */
  async pedir(rol, entrada, comprobacionesExtra = () => []) {
    let ultimo = null;
    for (let vuelta = 1; vuelta <= 2; vuelta += 1) {
      const salida = await this.#llamar(rol, entrada);
      const forma = comprobarSalidaDeAgente(rol, salida);
      const extra = forma.ok ? [].concat(comprobacionesExtra(salida)) : [];
      const bloqueantes = [
        ...forma.bloqueantes,
        ...extra.filter((c) => !c.ok && c.severidad === 'bloqueante'),
      ];

      this.registro.push({ rol, vuelta, ok: bloqueantes.length === 0 });

      if (bloqueantes.length === 0) {
        return { salida, comprobaciones: [...forma.comprobaciones, ...extra] };
      }
      ultimo = bloqueantes;
    }
    throw new ParadaDelProceso(
      `el rol ${rol} no supera las comprobaciones deterministas dos veces seguidas`,
      ultimo.flatMap((c) => c.detalles.map((d) => `${c.id}: ${d}`)),
    );
  }
}
