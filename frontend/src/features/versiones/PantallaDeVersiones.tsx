import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { publicarVersion, verPuerta, verVersiones } from "../../compartido/api/cliente";
import type { Fallo } from "../../compartido/api/fallos";
import type { PuertaDePublicacion, VersionDeLaObra } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { Icono } from "../../compartido/componentes/Icono";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { useConsulta } from "../../compartido/usar-consulta";
import "./versiones.css";

// Las versiones de la obra: de dónde sale cada una, qué cambió, si terminó y
// cuál es la publicada; publicar (SPEC2 RF-73, RF-74). La puerta se consulta
// por detrás: «Publicar» solo aparece cuando la versión está lista.
export function PantallaDeVersiones() {
  const { idObra = "" } = useParams();
  const [vuelta, setVuelta] = useState(0);
  const consulta = useConsulta(() => verVersiones(idObra), `${idObra}#${vuelta}`);

  return (
    <>
      <Cabecera pantalla="Versiones" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina versiones">
        <header className="versiones__cabecera">
          <span className="versiones__antetitulo">Historia de la obra</span>
          <h1>Versiones</h1>
          <p>Cada vez que la novela se reescribe nace una versión nueva; las anteriores se conservan enteras.</p>
        </header>
        {consulta.estado === "fallo" && (
          <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar}>
            {consulta.fallo.tipo === "rechazo" && <Link to="/">Ir al taller</Link>}
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

const fecha = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

function cuando(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const dia = new Date(iso);
  return Number.isNaN(dia.getTime()) ? null : fecha.format(dia);
}

type Accion =
  | { estado: "quieta" }
  | { estado: "en_curso"; que: string }
  | { estado: "publicada"; comprobacion: PuertaDePublicacion["comprobacion_formal"] }
  | { estado: "fallo"; fallo: Fallo };

type Lista = "comprobando" | "lista" | "no_lista";

type PropsDeTarjeta = { idObra: string; version: VersionDeLaObra; alPublicar: () => void };

function TarjetaDeVersion({ idObra, version, alPublicar }: PropsDeTarjeta) {
  const [accion, setAccion] = useState<Accion>({ estado: "quieta" });
  const publicable = version.terminada && !version.publicada;
  const [lista, setLista] = useState<Lista>("comprobando");

  useEffect(() => {
    if (!publicable) return;
    let activa = true;
    void verPuerta(idObra, version.numero).then((resultado) => {
      // Sin respuesta de la puerta no se esconde nada: publicar lo decide el servidor.
      if (activa) setLista(!resultado.ok || resultado.datos.pasa ? "lista" : "no_lista");
    });
    return () => {
      activa = false;
    };
  }, [idObra, version.numero, publicable]);

  async function publicar() {
    setAccion({ estado: "en_curso", que: "Publicando" });
    const resultado = await publicarVersion(idObra, version.numero);
    if (resultado.ok) {
      setAccion({ estado: "publicada", comprobacion: resultado.datos.comprobacion_formal });
      alPublicar();
    } else if (resultado.puerta) {
      setLista("no_lista");
      setAccion({ estado: "quieta" });
    } else {
      setAccion({ estado: "fallo", fallo: resultado.fallo });
    }
  }

  const ocupada = accion.estado === "en_curso";
  const creada = cuando(version.creada_en);
  return (
    <li className="version" aria-label={`Versión ${version.numero}`} data-publicada={version.publicada}>
      <span className="version__hito" aria-hidden="true">
        <Icono nombre={version.publicada ? "marcador" : version.terminada ? "hecho" : "pluma"} tamano={16} />
      </span>
      <div className="version__tarjeta">
        <div className="version__cabeza">
          <h2>Versión {version.numero}</h2>
          {version.publicada && <span className="version__marca">Publicada</span>}
          <span className="version__estado" data-terminada={version.terminada}>
            {version.terminada ? "Terminada" : "En producción"}
          </span>
          {creada && <span className="version__fecha">{creada}</span>}
        </div>
        <p className="version__origen">{deDondeSale(version)}</p>
        {version.base !== null && (
          <p className="version__cambiados">Capítulos que reescribe: {version.capitulos_cambiados.join(", ") || "ninguno"}.</p>
        )}
        <div className="version__acciones">
          <Link
            className="boton"
            to={`/obras/${encodeURIComponent(idObra)}/manuscrito${version.base !== null ? `?version=${version.numero}` : ""}`}
          >
            <Icono nombre="libro" /> Leerla
          </Link>
          {publicable && lista === "lista" && (
            <button type="button" className="principal" onClick={publicar} disabled={ocupada}>
              <Icono nombre="marcador" /> Publicar
            </button>
          )}
          {publicable && lista === "no_lista" && (
            <span className="version__pendiente">
              <Icono nombre="reloj" tamano={15} /> Pendiente de publicar
            </span>
          )}
        </div>
        {accion.estado === "en_curso" && <Espera que={accion.que} />}
        {accion.estado === "publicada" && (
          <p className="version__aviso" role="status">
            Publicada. Es la que se lee sin pedir versión.
            <SinComprobacionFormal comprobacion={accion.comprobacion} />
          </p>
        )}
        {accion.estado === "fallo" && <AvisoDeFallo fallo={accion.fallo} />}
      </div>
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
