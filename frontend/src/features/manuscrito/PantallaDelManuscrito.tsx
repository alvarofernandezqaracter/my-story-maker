import { Fragment, useState } from "react";
import { Link, useParams } from "react-router";
import { leerManuscrito, verObra, type Resultado } from "../../compartido/api/cliente";
import type { FichaDeObra, Manuscrito } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { Espera } from "../../compartido/componentes/Espera";
import { useConsulta } from "../../compartido/usar-consulta";
import { agrupar } from "./agrupar";
import "./manuscrito.css";

type Lectura = { ficha: FichaDeObra; manuscrito: Manuscrito };

async function pedirLectura(idObra: string): Promise<Resultado<Lectura>> {
  const [ficha, manuscrito] = await Promise.all([verObra(idObra), leerManuscrito(idObra)]);
  if (!ficha.ok) return ficha;
  if (!manuscrito.ok) return manuscrito;
  return { ok: true, datos: { ficha: ficha.datos, manuscrito: manuscrito.datos } };
}

// El manuscrito aceptado, en orden y cómodo de leer seguido (SPEC2 §4.3). Se
// puede leer una obra a medio producir: lo que hay es lo que se ve.
export function PantallaDelManuscrito() {
  const { idObra = "" } = useParams();
  const [vuelta, setVuelta] = useState(0);
  const consulta = useConsulta(() => pedirLectura(idObra), `${idObra}#${vuelta}`);
  const enlaceAlAvance = `/obras/${encodeURIComponent(idObra)}`;

  if (consulta.datos === null) {
    return (
      <>
        <Cabecera pantalla="Lectura" />
        <MenuDeObra idObra={idObra} />
        <main className="pagina">
          {consulta.estado === "fallo" ? (
            consulta.fallo.tipo === "sin_servidor" ? (
              <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar}>
                <span>Lo vuelvo a intentar solo cada pocos segundos.</span>
              </AvisoDeFallo>
            ) : (
              <AvisoDeFallo fallo={consulta.fallo}>
                <Link to="/">Ir al encargo</Link>
              </AvisoDeFallo>
            )
          ) : (
            <Espera que="Cargando el manuscrito" />
          )}
        </main>
      </>
    );
  }

  const { ficha, manuscrito } = consulta.datos;
  const capitulos = agrupar(manuscrito.unidades);

  return (
    <>
      <Cabecera pantalla="Lectura" />
        <MenuDeObra idObra={idObra} />
      <main className="pagina lectura">
        <header className="lectura__cabecera">
          <h1>{ficha.titulo}</h1>
          <dl className="lectura__recuento" aria-label="Recuento de la obra">
            <div>
              <dt>Capítulos cerrados</dt>
              <dd>{ficha.capitulos_cerrados}</dd>
            </div>
            <div>
              <dt>Capítulos marcados</dt>
              <dd>{ficha.capitulos_marcados}</dd>
            </div>
            <div>
              <dt>Críticas abiertas</dt>
              <dd>{ficha.criticas_abiertas}</dd>
            </div>
          </dl>
          <div className="lectura__acciones">
            <button type="button" onClick={() => setVuelta((v) => v + 1)} disabled={consulta.estado === "cargando"}>
              {consulta.estado === "cargando" ? "Buscando…" : "Buscar texto nuevo"}
            </button>
            <Link to={enlaceAlAvance}>Ver el avance</Link>
          </div>
          {consulta.estado === "fallo" && (
            <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar} />
          )}
        </header>

        {capitulos.length === 0 ? (
          <p className="lectura__vacia">
            Aún no hay ningún capítulo aceptado. Aparecerá aquí en cuanto se cierre el primero.{" "}
            <Link to={enlaceAlAvance}>Ver el avance</Link>
          </p>
        ) : (
          <div className="lectura__cuerpo">
            <nav className="indice" aria-label="Índice de capítulos">
              <details open className="indice__desplegable">
                <summary>Capítulos</summary>
                <ol>
                  {capitulos.map((c) => (
                    <li key={c.capitulo}>
                      <a href={`#capitulo-${c.capitulo}`}>
                        Capítulo {c.capitulo}
                        {c.marcado && <span className="indice__marca"> · con defectos</span>}
                      </a>
                    </li>
                  ))}
                </ol>
              </details>
            </nav>

            <div className="texto">
              {capitulos.map((capitulo, i) => {
                const anterior = capitulos[i - 1];
                const siguiente = capitulos[i + 1];
                return (
                  <article
                    key={capitulo.capitulo}
                    id={`capitulo-${capitulo.capitulo}`}
                    className="capitulo"
                    data-marcado={capitulo.marcado}
                  >
                    <h2>Capítulo {capitulo.capitulo}</h2>
                    {capitulo.marcado && (
                      <p className="capitulo__aviso" role="note">
                        Este capítulo tiene defectos sin resolver. Todavía no se puede ver cuáles.
                      </p>
                    )}
                    {capitulo.escenas.map((escena, j) => (
                      <Fragment key={escena.escena + j}>
                        {j > 0 && (
                          <p className="separador" aria-hidden="true">
                            ⁂
                          </p>
                        )}
                        <section className="escena" aria-label={`Escena ${escena.escena}`}>
                          {escena.parrafos.map((parrafo, k) => (
                            <p key={k}>{parrafo}</p>
                          ))}
                        </section>
                      </Fragment>
                    ))}
                    <nav className="capitulo__navegacion" aria-label="Entre capítulos">
                      {anterior ? (
                        <a href={`#capitulo-${anterior.capitulo}`}>← Capítulo anterior</a>
                      ) : (
                        <span />
                      )}
                      {siguiente && <a href={`#capitulo-${siguiente.capitulo}`}>Capítulo siguiente →</a>}
                    </nav>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </>
  );
}
