import { useState } from "react";
import { Link, useParams } from "react-router";
import { verTrazas } from "../../compartido/api/cliente";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { useConsulta } from "../../compartido/usar-consulta";
import { agruparPorCapitulo, duracion, veredictoDeLosHooks, type Veredicto } from "./agrupar";
import "./tareas.css";

const VEREDICTO: Record<Veredicto, string> = {
  pasa: "Pasó",
  no_pasa: "No pasó",
  sin_hooks: "—",
};

const celda = (valor: string | null) => valor ?? "—";

// Lo que ya se ha hecho en la obra, tarea por tarea y agrupado por capítulo
// (SPEC2 RF-26). Solo lo esencial: quién, qué, dónde, cuánto tardó y si pasó
// los hooks.
export function PantallaDeTareas() {
  const { idObra = "" } = useParams();
  const [vuelta, setVuelta] = useState(0);
  const consulta = useConsulta(() => verTrazas(idObra), `${idObra}#${vuelta}`);

  return (
    <>
      <Cabecera pantalla="Tareas" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina tareas-hechas">
        <header className="tareas-hechas__cabecera">
          <h1>Tareas</h1>
          <button
            type="button"
            onClick={() => setVuelta((v) => v + 1)}
            disabled={consulta.estado === "cargando"}
          >
            {consulta.estado === "cargando" ? "Actualizando…" : "Actualizar la lista"}
          </button>
        </header>

        {consulta.estado === "fallo" &&
          (consulta.fallo.tipo === "sin_servidor" ? (
            <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar}>
              <span>Lo vuelvo a intentar solo cada pocos segundos.</span>
            </AvisoDeFallo>
          ) : (
            <AvisoDeFallo fallo={consulta.fallo}>
              <Link to="/">Ir al encargo</Link>
            </AvisoDeFallo>
          ))}

        {consulta.datos === null ? (
          consulta.estado === "cargando" && <Espera que="Cargando las tareas" />
        ) : consulta.datos.length === 0 ? (
          <p className="tareas-hechas__vacia">Todavía no se ha hecho ninguna tarea en esta obra.</p>
        ) : (
          agruparPorCapitulo(consulta.datos).map((grupo, i) => (
            <section
              key={`${grupo.capitulo ?? "obra"}-${i}`}
              className="grupo-de-tareas"
              aria-label={grupo.capitulo === null ? "De la obra" : `Capítulo ${grupo.capitulo}`}
            >
              <h2>{grupo.capitulo === null ? "De la obra" : `Capítulo ${grupo.capitulo}`}</h2>
              <div className="tabla-envoltorio">
                <table className="tabla-de-tareas">
                  <thead>
                    <tr>
                      <th scope="col">Rol</th>
                      <th scope="col">Tarea</th>
                      <th scope="col">Escena</th>
                      <th scope="col">Duración</th>
                      <th scope="col">Hooks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grupo.tareas.map((traza) => {
                      const veredicto = veredictoDeLosHooks(traza);
                      return (
                        <tr key={traza.id}>
                          <td>{celda(traza.rol)}</td>
                          <td>{celda(traza.tarea)}</td>
                          <td>{celda(traza.escena)}</td>
                          <td>{duracion(traza)}</td>
                          <td className={`veredicto veredicto--${veredicto}`}>{VEREDICTO[veredicto]}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))
        )}
      </main>
    </>
  );
}
