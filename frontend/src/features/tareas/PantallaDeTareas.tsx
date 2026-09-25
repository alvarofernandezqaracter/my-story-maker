import { useState } from "react";
import { Link, useParams } from "react-router";
import { verTrazas } from "../../compartido/api/cliente";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { Icono } from "../../compartido/componentes/Icono";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { useConsulta } from "../../compartido/usar-consulta";
import { agruparPorCapitulo, duracion, legible, tiempoTotal } from "./agrupar";
import "./tareas.css";

function tono(texto: string): number {
  let h = 0;
  for (let i = 0; i < texto.length; i++) h = (h * 31 + texto.charCodeAt(i)) % 360;
  return h;
}

// Lo que ya se ha hecho en la obra, tarea por tarea y agrupado por capítulo
// (SPEC2 RF-26). Solo lo esencial: quién, qué, dónde y cuánto tardó.
export function PantallaDeTareas() {
  const { idObra = "" } = useParams();
  const [vuelta, setVuelta] = useState(0);
  const consulta = useConsulta(() => verTrazas(idObra), `${idObra}#${vuelta}`);
  const trazas = consulta.datos;

  return (
    <>
      <Cabecera pantalla="Tareas" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina tareas-hechas">
        <header className="tareas-hechas__cabecera">
          <div>
            <span className="tareas-hechas__antetitulo">Entre bastidores</span>
            <h1>Tareas</h1>
            <p>Lo que ha hecho cada agente del equipo para escribir esta novela.</p>
          </div>
          <button type="button" onClick={() => setVuelta((v) => v + 1)} disabled={consulta.estado === "cargando"}>
            {consulta.estado === "cargando" ? "Actualizando…" : "Actualizar la lista"}
          </button>
        </header>

        {trazas !== null && trazas.length > 0 && (
          <dl className="tareas-hechas__resumen">
            <div>
              <dt>Tareas hechas</dt>
              <dd>{trazas.length}</dd>
            </div>
            <div>
              <dt>Agentes distintos</dt>
              <dd>{new Set(trazas.map((t) => t.rol)).size}</dd>
            </div>
            <div>
              <dt>Tiempo de trabajo</dt>
              <dd>{tiempoTotal(trazas)}</dd>
            </div>
          </dl>
        )}

        {consulta.estado === "fallo" &&
          (consulta.fallo.tipo === "sin_servidor" ? (
            <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar}>
              <span>Lo vuelvo a intentar solo cada pocos segundos.</span>
            </AvisoDeFallo>
          ) : (
            <AvisoDeFallo fallo={consulta.fallo}>
              <Link to="/">Ir al taller</Link>
            </AvisoDeFallo>
          ))}

        {trazas === null ? (
          consulta.estado === "cargando" && <Espera que="Cargando las tareas" />
        ) : trazas.length === 0 ? (
          <p className="tareas-hechas__vacia">Todavía no se ha hecho ninguna tarea en esta obra.</p>
        ) : (
          agruparPorCapitulo(trazas).map((grupo, i) => (
            <section
              key={`${grupo.capitulo ?? "obra"}-${i}`}
              className="grupo-de-tareas"
              aria-label={grupo.capitulo === null ? "De la obra" : `Capítulo ${grupo.capitulo}`}
            >
              <h2>
                <Icono nombre={grupo.capitulo === null ? "capas" : "libro"} tamano={17} />
                {grupo.capitulo === null ? "De la obra" : `Capítulo ${grupo.capitulo}`}
                <span className="grupo-de-tareas__cuenta">
                  {grupo.tareas.length} {grupo.tareas.length === 1 ? "tarea" : "tareas"}
                </span>
              </h2>
              <div className="tabla-envoltorio">
                <table className="tabla-de-tareas">
                  <thead>
                    <tr>
                      <th scope="col">Agente</th>
                      <th scope="col">Tarea</th>
                      <th scope="col">Escena</th>
                      <th scope="col">Duración</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grupo.tareas.map((traza) => (
                      <tr key={traza.id}>
                        <td>
                          <span className="agente">
                            <span
                              className="agente__punto"
                              style={{ background: `hsl(${tono(traza.rol ?? "")} 60% 55%)` }}
                              aria-hidden="true"
                            />
                            {legible(traza.rol)}
                          </span>
                        </td>
                        <td>{legible(traza.tarea)}</td>
                        <td className="tabla-de-tareas__escena">{traza.escena ?? "—"}</td>
                        <td className="tabla-de-tareas__duracion">{duracion(traza)}</td>
                      </tr>
                    ))}
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
