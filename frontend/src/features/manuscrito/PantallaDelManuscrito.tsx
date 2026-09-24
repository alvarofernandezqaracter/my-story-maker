import { Fragment, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import {
  enlaceDelPdf,
  leerManuscrito,
  verHechos,
  verObra,
  verVersiones,
  type Resultado,
} from "../../compartido/api/cliente";
import type {
  FichaDeObra,
  HechoDeLaBiblia,
  Manuscrito,
  VersionDeLaObra,
} from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { Espera } from "../../compartido/componentes/Espera";
import { useConsulta } from "../../compartido/usar-consulta";
import { agrupar } from "./agrupar";
import { Biblia } from "./Biblia";
import { CriticasDelCapitulo } from "./CriticasDelCapitulo";
import { Portada } from "./Portada";
import "./manuscrito.css";

type Lectura = {
  ficha: FichaDeObra;
  manuscrito: Manuscrito;
  hechos: HechoDeLaBiblia[];
  versiones: VersionDeLaObra[];
};

async function pedirLectura(idObra: string, version?: number): Promise<Resultado<Lectura>> {
  const [ficha, manuscrito, versiones] = await Promise.all([
    verObra(idObra),
    leerManuscrito(idObra, version),
    verVersiones(idObra),
  ]);
  if (!ficha.ok) return ficha;
  if (!manuscrito.ok) return manuscrito;
  if (!versiones.ok) return versiones;
  // La biblia es la de la versión que se lee, la pedida o la de referencia.
  const hechos = await verHechos(idObra, manuscrito.datos.version);
  if (!hechos.ok) return hechos;
  return {
    ok: true,
    datos: { ficha: ficha.datos, manuscrito: manuscrito.datos, hechos: hechos.datos, versiones: versiones.datos },
  };
}

function versionDeLaDireccion(valor: string | null): number | undefined {
  const numero = Number(valor);
  return valor !== null && Number.isInteger(numero) && numero >= 1 ? numero : undefined;
}

// El manuscrito aceptado, en orden y cómodo de leer seguido (SPEC2 §4.3), con
// su portada, su biblia, las críticas de cada capítulo y la descarga (§4.5 a
// §4.9). Se puede leer una obra a medio producir: lo que hay es lo que se ve.
export function PantallaDelManuscrito() {
  const { idObra = "" } = useParams();
  const [parametros, setParametros] = useSearchParams();
  const versionPedida = versionDeLaDireccion(parametros.get("version"));
  const [vuelta, setVuelta] = useState(0);
  const consulta = useConsulta(
    () => pedirLectura(idObra, versionPedida),
    `${idObra}#${versionPedida ?? "referencia"}#${vuelta}`,
  );
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
                <Link to="/">Ir al taller</Link>
              </AvisoDeFallo>
            )
          ) : (
            <Espera que="Cargando el manuscrito" />
          )}
        </main>
      </>
    );
  }

  const { ficha, manuscrito, hechos, versiones } = consulta.datos;
  const capitulos = agrupar(manuscrito.unidades);
  const leida = versiones.find((v) => v.numero === manuscrito.version);
  // Lo que cambió respecto de su base, tal como lo sirve el servidor (RF-70).
  const cambiados = new Set(leida && leida.base !== null ? leida.capitulos_cambiados : []);

  function elegirVersion(valor: string) {
    const siguientes = new URLSearchParams(parametros);
    if (valor === "") siguientes.delete("version");
    else siguientes.set("version", valor);
    setParametros(siguientes);
  }

  return (
    <>
      <Cabecera pantalla="Lectura" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina lectura">
        <header className="lectura__cabecera">
          <Portada ficha={ficha} />
          <p className="lectura__version" aria-live="polite">
            Versión {manuscrito.version}
            {manuscrito.publicada ? " · publicada" : " · sin publicar"}
          </p>
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
            <label className="lectura__selector">
              Leer la versión{" "}
              <select value={versionPedida ?? ""} onChange={(e) => elegirVersion(e.target.value)}>
                <option value="">La de referencia</option>
                {versiones.map((v) => (
                  <option key={v.numero} value={v.numero}>
                    Versión {v.numero}
                    {v.publicada ? " · publicada" : ""}
                  </option>
                ))}
              </select>
            </label>
            <a className="boton" href={enlaceDelPdf(idObra, manuscrito.version)} download>
              Descargar PDF
            </a>
            <button type="button" onClick={() => setVuelta((v) => v + 1)} disabled={consulta.estado === "cargando"}>
              {consulta.estado === "cargando" ? "Buscando…" : "Buscar texto nuevo"}
            </button>
            <Link to={enlaceAlAvance}>Ver el avance</Link>
          </div>
          {consulta.estado === "fallo" && (
            <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar} />
          )}
        </header>

        <Biblia idObra={idObra} hechos={hechos} />

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
                        {cambiados.has(c.capitulo) && <span className="indice__cambio"> · cambió</span>}
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
                    data-cambiado={cambiados.has(capitulo.capitulo)}
                  >
                    <h2>Capítulo {capitulo.capitulo}</h2>
                    {cambiados.has(capitulo.capitulo) && (
                      <p className="capitulo__cambio">
                        Reescrito en esta versión respecto de la {leida?.base}.
                      </p>
                    )}
                    {capitulo.marcado && (
                      <p className="capitulo__aviso" role="note">
                        Este capítulo tiene defectos sin resolver. Se ven en «Ver críticas».
                      </p>
                    )}
                    <CriticasDelCapitulo idObra={idObra} capitulo={capitulo.capitulo} version={manuscrito.version} />
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
