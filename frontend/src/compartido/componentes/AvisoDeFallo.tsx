import type { ReactNode } from "react";
import type { Fallo } from "../api/fallos";

type Props = {
  fallo: Fallo;
  /** Si se pasa, aparece el botón «Reintentar». */
  reintentar?: () => void;
  /** Lo que el mensaje propone además de reintentar. */
  children?: ReactNode;
};

// Pinta el mensaje del servidor tal cual (SPEC2 RF-61) y distingue un fallo de
// red —aviso— de un rechazo del servidor —error— (RF-62).
export function AvisoDeFallo({ fallo, reintentar, children }: Props) {
  const clase = fallo.tipo === "sin_servidor" ? "aviso aviso--red" : "aviso aviso--rechazo";
  return (
    <div className={clase} role="alert" data-tipo={fallo.tipo}>
      <p className="aviso__mensaje">{fallo.mensaje}</p>
      {fallo.tipo === "rechazo" && fallo.campos.length > 0 && (
        <ul className="aviso__campos">
          {fallo.campos.map((campo) => (
            <li key={campo}>
              <code>{campo}</code>
            </li>
          ))}
        </ul>
      )}
      {(reintentar || children) && (
        <div className="aviso__acciones">
          {reintentar && (
            <button type="button" onClick={reintentar}>
              Reintentar
            </button>
          )}
          {children}
        </div>
      )}
    </div>
  );
}
