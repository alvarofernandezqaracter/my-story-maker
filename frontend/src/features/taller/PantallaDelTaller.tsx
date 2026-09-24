import { useState } from "react";
import { Link } from "react-router";
import { listarObras } from "../../compartido/api/cliente";
import type { ObraDelTaller } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { ETIQUETA_DE_SITUACION, ORDEN_DE_SITUACIONES } from "../../compartido/situacion";
import { useSondeo } from "../../compartido/usar-sondeo";
import { TarjetaDeObra } from "./TarjetaDeObra";
import "./taller.css";

export const PERIODO_DEL_TALLER_MS = 5000;

function casa(obra: ObraDelTaller, texto: string): boolean {
  if (!texto) return true;
  return [obra.titulo, obra.epoca, obra.destinatario ?? ""].some((v) => v.toLowerCase().includes(texto));
}

// El taller: todas las obras en un tablero, una columna por situación (SPEC2
// §4.11). La columna la dice el servidor; aquí solo se reparte y se pinta.
// Las tarjetas no se arrastran (D-26).
export function PantallaDelTaller() {
  const consulta = useSondeo(listarObras, "taller", PERIODO_DEL_TALLER_MS);
  const [filtro, setFiltro] = useState("");
  const obras = consulta.datos;

  return (
    <>
      <Cabecera pantalla="Todas las obras" />
      <main className="pagina pagina--ancha taller">
        <header className="taller__cabecera">
          <div>
            <h1>Taller</h1>
            <p className="taller__resumen">
              {obras === null
                ? "Todas las obras de la instalación, por su situación"
                : resumen(obras)}
            </p>
          </div>
          {obras !== null && obras.length > 0 && (
            <label className="taller__filtro">
              <span className="visualmente-oculto">Filtrar obras</span>
              <input
                type="search"
                placeholder="Filtrar por título, época o destinatario"
                value={filtro}
                onChange={(e) => setFiltro(e.target.value)}
              />
            </label>
          )}
        </header>

        {consulta.estado === "fallo" && (
          <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar}>
            {obras !== null && <span>Lo que ves es lo último que llegó.</span>}
          </AvisoDeFallo>
        )}

        {obras === null && consulta.estado !== "fallo" && <Espera que="Cargando las obras" />}

        {obras !== null && obras.length === 0 && (
          <div className="taller__vacio">
            <h2>Todavía no hay ninguna obra</h2>
            <p>Cuando encargues una, aparecerá aquí con su situación.</p>
            <Link to="/encargo" className="boton-principal">
              Encarga la primera
            </Link>
          </div>
        )}

        {obras !== null && obras.length > 0 && (
          <div className="tablero" role="list" aria-label="Obras por situación">
            {ORDEN_DE_SITUACIONES.map((situacion) => {
              const suyas = obras.filter((o) => o.situacion === situacion && casa(o, filtro.trim().toLowerCase()));
              const titulo = ETIQUETA_DE_SITUACION[situacion];
              return (
                <section
                  key={situacion}
                  className="columna"
                  data-situacion={situacion}
                  role="listitem"
                  aria-label={`${titulo}: ${suyas.length}`}
                >
                  <header className="columna__cabecera">
                    <h2>{titulo}</h2>
                    <span className="columna__cuenta">{suyas.length}</span>
                  </header>
                  <div className="columna__tarjetas">
                    {suyas.length === 0 ? (
                      <p className="columna__vacia">Ninguna</p>
                    ) : (
                      suyas.map((obra) => <TarjetaDeObra key={obra.id_obra} obra={obra} />)
                    )}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}

function resumen(obras: ObraDelTaller[]): string {
  const total = `${obras.length} ${obras.length === 1 ? "obra" : "obras"}`;
  const cuenta = (s: ObraDelTaller["situacion"]) => obras.filter((o) => o.situacion === s).length;
  return `${total} · ${cuenta("en_produccion")} en producción · ${cuenta("detenida")} detenidas`;
}
