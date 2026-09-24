import { useState } from "react";
import { Link, useParams } from "react-router";
import { publicarVersion, verPuerta, verVersiones } from "../../compartido/api/cliente";
import type { Fallo } from "../../compartido/api/fallos";
import type { PuertaDePublicacion, VersionDeLaObra } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { useConsulta } from "../../compartido/usar-consulta";
import "./versiones.css";

// Las versiones de la obra: de dónde sale cada una, qué cambió, si terminó y
// cuál es la publicada; publicar y comprobar la puerta (SPEC2 RF-73, RF-74).
export function PantallaDeVersiones() {
  const { idObra = "" } = useParams();
  const [vuelta, setVuelta] = useState(0);
  const consulta = useConsulta(() => verVersiones(idObra), `${idObra}#${vuelta}`);

  return (
    <>
      <Cabecera pantalla="Versiones" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina versiones">
        <h1>Versiones</h1>
        {consulta.estado === "fallo" && (
          <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar}>
            {consulta.fallo.tipo === "rechazo" && <Link to="/">Ir al encargo</Link>}
          </AvisoDeFallo>
        )}
        {consulta.datos === null ? (
          consulta.estado !== "fallo" && <Espera que="Cargando las versiones" />
        ) : (
          <ol className="versiones__lista">
            {[...consulta.datos].reverse().map((version) => (
              <TarjetaDeVersion
                key={version.numero}
                idObra={idObra}
                version={version}
                alPublicar={() => setVuelta((v) => v + 1)}
              />
            ))}
          </ol>
        )}
      </main>
    </>
  );
}

function deDondeSale(version: VersionDeLaObra): string {
  if (version.base === null) return "Nace con el alta de la obra.";
  if (version.cambio) {
    return `Sale de la versión ${version.base} por un cambio del lector: «${version.cambio.anterior}» pasa a llamarse «${version.cambio.nuevo}».`;
  }
  return `Sale de la versión ${version.base}, rehecha desde el capítulo ${version.capitulos_cambiados[0] ?? "?"}.`;
}

type Accion =
  | { estado: "quieta" }
  | { estado: "en_curso"; que: string }
  | { estado: "puerta"; puerta: PuertaDePublicacion }
  | { estado: "publicada"; comprobacion: PuertaDePublicacion["comprobacion_formal"] }
  | { estado: "fallo"; fallo: Fallo; puerta: PuertaDePublicacion | null };

type PropsDeTarjeta = { idObra: string; version: VersionDeLaObra; alPublicar: () => void };

function TarjetaDeVersion({ idObra, version, alPublicar }: PropsDeTarjeta) {
  const [accion, setAccion] = useState<Accion>({ estado: "quieta" });

  async function comprobar() {
    setAccion({ estado: "en_curso", que: "Pasando la puerta" });
    const resultado = await verPuerta(idObra, version.numero);
    setAccion(resultado.ok ? { estado: "puerta", puerta: resultado.datos } : { estado: "fallo", fallo: resultado.fallo, puerta: null });
  }

  async function publicar() {
    setAccion({ estado: "en_curso", que: "Publicando" });
    const resultado = await publicarVersion(idObra, version.numero);
    if (resultado.ok) {
      setAccion({ estado: "publicada", comprobacion: resultado.datos.comprobacion_formal });
      alPublicar();
    } else {
      setAccion({ estado: "fallo", fallo: resultado.fallo, puerta: resultado.puerta });
    }
  }

  const ocupada = accion.estado === "en_curso";
  return (
    <li className="version" aria-label={`Versión ${version.numero}`} data-publicada={version.publicada}>
      <div className="version__cabeza">
        <h2>Versión {version.numero}</h2>
        {version.publicada && <span className="version__marca">Publicada</span>}
        <span className="version__estado">{version.terminada ? "Terminada" : "En producción"}</span>
      </div>
      <p>{deDondeSale(version)}</p>
      {version.base !== null && (
        <p className="version__cambiados">
          Capítulos que reescribe: {version.capitulos_cambiados.join(", ") || "ninguno"}.{" "}
          <Link to={`/obras/${encodeURIComponent(idObra)}/manuscrito?version=${version.numero}`}>Leerla</Link>
        </p>
      )}
      <div className="version__acciones">
        <button type="button" onClick={comprobar} disabled={ocupada}>
          Comprobar la puerta
        </button>
        {version.terminada && !version.publicada && (
          <button type="button" onClick={publicar} disabled={ocupada}>
            Publicar
          </button>
        )}
      </div>
      {accion.estado === "en_curso" && <Espera que={accion.que} />}
      {accion.estado === "puerta" && <ResultadoDeLaPuerta puerta={accion.puerta} />}
      {accion.estado === "publicada" && (
        <p className="version__aviso" role="status">
          Publicada. Es la que se lee sin pedir versión.
        </p>
      )}
      {accion.estado === "publicada" && <SinComprobacionFormal comprobacion={accion.comprobacion} />}
      {accion.estado === "fallo" && (
        <>
          <AvisoDeFallo fallo={accion.fallo} />
          {accion.puerta && <ResultadoDeLaPuerta puerta={accion.puerta} />}
        </>
      )}
    </li>
  );
}

// Sin Lean en el servidor la versión se publica igual, pero quien publica tiene
// que verlo (SPEC1 RF-155, SPEC2 RF-74).
function SinComprobacionFormal({ comprobacion }: { comprobacion: PuertaDePublicacion["comprobacion_formal"] }) {
  if (comprobacion !== "sin_comprobacion") return null;
  return (
    <span className="puerta__sin-comprobacion">
      {" "}Sin comprobación formal: Lean no está instalado en el servidor y la cronología no se ha demostrado.
    </span>
  );
}

// Cada fallo con su validador tal como lo nombra el servidor, su capítulo y su
// detalle. No se enumeran los validadores: uno nuevo sale solo (SPEC2 D-22).
function ResultadoDeLaPuerta({ puerta }: { puerta: PuertaDePublicacion }) {
  if (puerta.pasa) {
    return (
      <p className="puerta puerta--pasa" role="status">
        Pasa la puerta{puerta.terminada ? "." : ", pero aún no ha terminado: no se puede publicar."}
        <SinComprobacionFormal comprobacion={puerta.comprobacion_formal} />
      </p>
    );
  }
  return (
    <div className="puerta puerta--no-pasa" role="status">
      <p>No pasa la puerta: {puerta.fallos.length === 1 ? "1 fallo" : `${puerta.fallos.length} fallos`}.</p>
      <ul aria-label={`Por qué no pasa la versión ${puerta.version}`}>
        {puerta.fallos.map((fallo, i) => (
          <li key={i}>
            <code>{fallo.validador}</code> · {fallo.capitulo === null ? "de la obra" : `capítulo ${fallo.capitulo}`} ·{" "}
            {fallo.detalle}
          </li>
        ))}
      </ul>
    </div>
  );
}
