import { useState } from "react";
import { verCriticasDelCapitulo } from "../../compartido/api/cliente";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Espera } from "../../compartido/componentes/Espera";
import { useConsulta } from "../../compartido/usar-consulta";

type Props = { idObra: string; capitulo: number; version: number };

// «Ver críticas»: se piden al pulsar, las del capítulo en la versión leída, y se
// pintan tal como vienen (SPEC2 RF-75, D-21).
export function CriticasDelCapitulo(props: Props) {
  const [abiertas, setAbiertas] = useState(false);
  return (
    <div className="criticas">
      <button type="button" className="criticas__boton" aria-expanded={abiertas} onClick={() => setAbiertas((a) => !a)}>
        {abiertas ? "Ocultar críticas" : "Ver críticas"}
      </button>
      {abiertas && <ListaDeCriticas {...props} />}
    </div>
  );
}

function ListaDeCriticas({ idObra, capitulo, version }: Props) {
  const consulta = useConsulta(
    () => verCriticasDelCapitulo(idObra, capitulo, version),
    `${idObra}#${capitulo}#${version}`,
  );
  if (consulta.estado === "fallo") return <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar} />;
  if (consulta.datos === null) return <Espera que="Cargando las críticas" />;
  if (consulta.datos.length === 0) return <p className="criticas__vacio">Este capítulo no tiene críticas.</p>;
  return (
    <ul className="criticas__lista" aria-label={`Críticas del capítulo ${capitulo}`}>
      {consulta.datos.map((critica) => (
        <li key={critica.id} className="critica" data-severidad={critica.severidad ?? undefined}>
          <p className="critica__cabeza">
            <code>{critica.dimension ?? "sin dimensión"}</code> · {critica.severidad ?? "sin severidad"} ·{" "}
            {critica.estado ?? "sin estado"}
            {critica.detectada_por && <> · la detectó {critica.detectada_por}</>}
          </p>
          {critica.evidencia && <blockquote className="critica__evidencia">{critica.evidencia}</blockquote>}
          {critica.accion_sugerida && <p className="critica__accion">{critica.accion_sugerida}</p>}
        </li>
      ))}
    </ul>
  );
}
