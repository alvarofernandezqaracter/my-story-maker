import { useState } from "react";
import { Link } from "react-router";
import { listarObras } from "../../compartido/api/cliente";
import type { ObraDelTaller } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { Icono } from "../../compartido/componentes/Icono";
import { Libro } from "../../compartido/componentes/Libro";
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
// Las tarjetas no se arrastran (D-26). Encima, las que ya se pueden leer, en
// una estantería.
export function PantallaDelTaller() {
  const consulta = useSondeo(listarObras, "taller", PERIODO_DEL_TALLER_MS);
  const [filtro, setFiltro] = useState("");
  const obras = consulta.datos;
  const leibles = (obras ?? []).filter((o) => o.situacion === "terminada" || o.situacion === "publicada");

  return (
    <>
      <Cabecera pantalla="Todas las obras" />
      <main className="pagina pagina--ancha taller">
        <header className="taller__cabecera">
          <div className="taller__saludo">
            <span className="seccion-antetitulo">Taller de novelas</span>
            <h1>Taller</h1>
            <p className="taller__resumen">
              {obras === null
                ? "Todas las obras de la instalación, por su situación"
                : resumen(obras)}
            </p>
          </div>
          {obras !== null && obras.length > 0 && (
            <dl className="taller__cifras" aria-label="El taller en cifras">
              <div>
                <dt>Obras</dt>
                <dd>{obras.length}</dd>
              </div>
              <div>
                <dt>Capítulos escritos</dt>
                <dd>{obras.reduce((s, o) => s + o.capitulos_cerrados, 0)}</dd>
              </div>
              <div>
                <dt>Listas para leer</dt>
                <dd>{leibles.length}</dd>
              </div>
            </dl>
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
            <Icono nombre="pluma" tamano={32} />
            <h2>Todavía no hay ninguna obra</h2>
            <p>Cuando encargues una, aparecerá aquí con su situación.</p>
            <Link to="/encargo" className="boton-principal">
              Encarga la primera
            </Link>
          </div>
        )}

        {leibles.length > 0 && (
          <section className="estanteria" aria-labelledby="estanteria-titulo">
            <div className="estanteria__cabecera">
              <h2 id="estanteria-titulo">
                <Icono nombre="libro" /> Tu biblioteca
              </h2>
              <p>Las novelas terminadas, listas para abrir y leer.</p>
            </div>
            <ul className="estanteria__baldas">
              {leibles.map((obra) => (
                <li key={obra.id_obra}>
                  <Link
                    to={`/obras/${encodeURIComponent(obra.id_obra)}/manuscrito`}
                    className="estanteria__libro"
                    aria-label={`Leer ${obra.titulo}`}
                  >
                    <Libro titulo={obra.titulo} subtitulo={obra.epoca} autor="Story Maker" tamano="media" />
                    <span className="estanteria__ficha" aria-hidden="true">
                      <span className="estanteria__epoca">{obra.epoca}</span>
                      {obra.destinatario && <span className="estanteria__para">Para {obra.destinatario}</span>}
                      <span className="estanteria__leer">
                        Leer <Icono nombre="derecha" tamano={14} />
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
              <li>
                <Link to="/encargo" className="estanteria__nuevo">
                  <Icono nombre="mas" tamano={28} />
                  <span>Encargar otra novela</span>
                </Link>
              </li>
            </ul>
          </section>
        )}

        {obras !== null && obras.length > 0 && (
          <section className="produccion" aria-labelledby="produccion-titulo">
            <div className="produccion__cabecera">
              <div>
                <h2 id="produccion-titulo">
                  <Icono nombre="tablero" /> Producción
                </h2>
                <p>Cada obra en la columna de su situación.</p>
              </div>
              <label className="taller__filtro">
                <Icono nombre="buscar" tamano={16} />
                <span className="visualmente-oculto">Filtrar obras</span>
                <input
                  type="search"
                  placeholder="Filtrar por título, época o destinatario"
                  value={filtro}
                  onChange={(e) => setFiltro(e.target.value)}
                />
              </label>
            </div>
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
                      <span className="columna__punto" aria-hidden="true" />
                      <h3>{titulo}</h3>
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
          </section>
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
