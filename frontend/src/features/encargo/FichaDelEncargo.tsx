import { GRUPOS, type Campo } from "./campos";
import { valorEnRuta } from "./peticion";

type Props = {
  valores: Record<string, string>;
  /** El brief que propuso la última pasada, tal cual; null si aún no hay pasada. */
  propuesto: Record<string, unknown> | null;
  /** Rutas que el servidor ha señalado: las que faltan y las rechazadas. */
  senaladas: ReadonlySet<string>;
  bloqueado: boolean;
  alCambiar: (ruta: string, texto: string) => void;
  alQuedarse: (ruta: string, valor: unknown) => void;
};

function comoTexto(valor: unknown): string {
  if (Array.isArray(valor)) return valor.map(String).join(", ");
  if (typeof valor === "object" && valor !== null) return JSON.stringify(valor);
  return String(valor);
}

function tieneValor(valor: unknown): boolean {
  if (valor === undefined || valor === null) return false;
  if (typeof valor === "string") return valor.trim() !== "";
  if (Array.isArray(valor)) return valor.length > 0;
  return true;
}

// El borrador por campos. Lo que la persona escribe aquí es lo único que va
// como `borrador`; lo que el sistema entendió se ofrece, no se copia solo.
export function FichaDelEncargo({
  valores,
  propuesto,
  senaladas,
  bloqueado,
  alCambiar,
  alQuedarse,
}: Props) {
  function renderCampo(campo: Campo) {
    const id = `campo-${campo.ruta}`;
    const texto = valores[campo.ruta] ?? "";
    const entendido = propuesto === null ? undefined : valorEnRuta(propuesto, campo.ruta);
    const ofrecer = texto.trim() === "" && tieneValor(entendido);
    const senalada = senaladas.has(campo.ruta);
    return (
      <div
        key={campo.ruta}
        className={senalada ? "campo campo--senalado" : "campo"}
        data-ruta={campo.ruta}
      >
        <label htmlFor={id}>
          {campo.etiqueta} <span className="ruta">{campo.ruta}</span>
        </label>
        {campo.clase === "texto" && (
          <input
            id={id}
            value={texto}
            disabled={bloqueado}
            onChange={(e) => alCambiar(campo.ruta, e.target.value)}
          />
        )}
        {campo.clase === "numero" && (
          <input
            id={id}
            type="number"
            inputMode="numeric"
            value={texto}
            disabled={bloqueado}
            onChange={(e) => alCambiar(campo.ruta, e.target.value)}
          />
        )}
        {(campo.clase === "largo" || campo.clase === "lista") && (
          <textarea
            id={id}
            rows={campo.clase === "lista" ? 3 : 2}
            value={texto}
            disabled={bloqueado}
            placeholder={campo.clase === "lista" ? "Uno por línea" : undefined}
            onChange={(e) => alCambiar(campo.ruta, e.target.value)}
          />
        )}
        {senalada && <span className="campo__senal">Revisa este campo</span>}
        {campo.ayuda && <small className="campo__ayuda">{campo.ayuda}</small>}
        {ofrecer && (
          <div className="entendido">
            <span>Entendido: {comoTexto(entendido)}</span>
            <button
              type="button"
              className="discreto"
              disabled={bloqueado}
              onClick={() => alQuedarse(campo.ruta, entendido)}
            >
              Quedármelo
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <section className="ficha" aria-label="Ficha del encargo">
      {GRUPOS.map((grupo) => (
        <fieldset key={grupo.titulo} className="ficha__grupo">
          <legend>{grupo.titulo}</legend>
          {grupo.campos.map(renderCampo)}
        </fieldset>
      ))}
    </section>
  );
}
