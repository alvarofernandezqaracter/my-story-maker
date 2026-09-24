import { useState } from "react";
import type { Aportacion } from "./peticion";

type Props = {
  aportaciones: Aportacion[];
  bloqueado: boolean;
  alQuitar: (id: string) => void;
  alPegar: (texto: string) => void;
  /** Envía la pasada; si hay algo escrito en el cuadro, va como mensaje nuevo. */
  alEnviar: (mensajeNuevo: string) => void;
};

// Lo que la persona aporta, en orden. Los textos pegados van en tarjeta propia,
// con su etiqueta, separados de los mensajes y de lo que contesta el sistema
// (SPEC2 RF-07).
export function Conversacion({ aportaciones, bloqueado, alQuitar, alPegar, alEnviar }: Props) {
  const [mensaje, setMensaje] = useState("");
  const [pegando, setPegando] = useState(false);
  const [pegado, setPegado] = useState("");

  const numeroDePegado = new Map<string, number>();
  for (const aportacion of aportaciones) {
    if (aportacion.clase === "pegado") numeroDePegado.set(aportacion.id, numeroDePegado.size + 1);
  }

  function enviar() {
    alEnviar(mensaje);
    setMensaje("");
  }

  function guardarPegado() {
    alPegar(pegado);
    setPegado("");
    setPegando(false);
  }

  return (
    <section className="conversacion" aria-label="Tu encargo">
      {aportaciones.length === 0 ? (
        <p className="conversacion__vacia">
          Cuéntame la novela que quieres encargar: para quién es, en qué época, de qué va. Si tienes
          una carta o una anécdota escrita, pégala entera.
        </p>
      ) : (
        <ol className="conversacion__lista">
          {aportaciones.map((aportacion) =>
            aportacion.clase === "mensaje" ? (
              <li key={aportacion.id} className="burbuja">
                <span className="burbuja__autor">Tú</span>
                <p className="burbuja__texto">{aportacion.texto}</p>
                <button
                  type="button"
                  className="discreto"
                  disabled={bloqueado}
                  onClick={() => alQuitar(aportacion.id)}
                >
                  Quitar
                </button>
              </li>
            ) : (
              <li key={aportacion.id} className="pegado" data-clase="pegado">
                <span className="pegado__etiqueta">
                  Texto pegado · {numeroDePegado.get(aportacion.id)}
                </span>
                <details>
                  <summary className="pegado__resumen">{aportacion.texto}</summary>
                  <p className="pegado__texto">{aportacion.texto}</p>
                </details>
                <button
                  type="button"
                  className="discreto"
                  disabled={bloqueado}
                  onClick={() => alQuitar(aportacion.id)}
                >
                  Quitar
                </button>
              </li>
            ),
          )}
        </ol>
      )}

      <div className="redactar">
        <label htmlFor="mensaje" className="visualmente-oculto">
          Escribe tu mensaje
        </label>
        <textarea
          id="mensaje"
          rows={3}
          placeholder="Escribe aquí…"
          value={mensaje}
          onChange={(e) => setMensaje(e.target.value)}
          disabled={bloqueado}
        />
        <div className="redactar__botones">
          <button type="button" className="principal" onClick={enviar} disabled={bloqueado}>
            Enviar
          </button>
          <button
            type="button"
            onClick={() => setPegando((p) => !p)}
            disabled={bloqueado}
            aria-expanded={pegando}
          >
            Pegar un texto
          </button>
        </div>
        {pegando && (
          <div className="redactar__pegar">
            <label htmlFor="pegado">Pega aquí una carta, una anécdota o cualquier texto tuyo</label>
            <textarea
              id="pegado"
              rows={10}
              value={pegado}
              onChange={(e) => setPegado(e.target.value)}
            />
            <div className="redactar__botones">
              <button type="button" onClick={guardarPegado} disabled={pegado.trim() === ""}>
                Añadir el texto
              </button>
              <button type="button" className="discreto" onClick={() => setPegando(false)}>
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
