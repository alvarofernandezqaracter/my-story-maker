import { useState } from "react";
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
import { Espera } from "../../compartido/componentes/Espera";
import { Icono } from "../../compartido/componentes/Icono";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { esNumeroEntre, leerPreferencia } from "../../compartido/preferencias";
import { useConsulta } from "../../compartido/usar-consulta";
import { agrupar } from "./agrupar";
import { Biblia } from "./Biblia";
import { minutosDeLectura, palabrasDe } from "./herramientas";
import { claveDeLaPosicion, Lector } from "./Lector";
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

function desplazarA(id: string) {
  document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
}

// El manuscrito aceptado, en orden y cómodo de leer seguido (SPEC2 §4.3), con
// su portada, su biblia y la descarga (§4.5 a §4.9). Se puede leer una obra a
// medio producir: lo que hay es lo que se ve.
export function PantallaDelManuscrito() {
  const { idObra = "" } = useParams();
  const [parametros, setParametros] = useSearchParams();
  const versionPedida = versionDeLaDireccion(parametros.get("version"));
  const [vuelta, setVuelta] = useState(0);
  const [guardado] = useState(() => leerPreferencia<number | null>(claveDeLaPosicion(idObra), null, esNumeroEntre(1, 9999)));
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
            <Espera que="Abriendo el libro" />
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
  const palabras = capitulos.reduce((suma, c) => suma + palabrasDe(c), 0);
  const continuar = guardado !== null && guardado > 1 && capitulos.some((c) => c.capitulo === guardado) ? guardado : null;
  const enProduccion = ficha.situacion === "en_produccion";

  function elegirVersion(valor: string) {
    const siguientes = new URLSearchParams(parametros);
    if (valor === "") siguientes.delete("version");
    else siguientes.set("version", valor);
    setParametros(siguientes);
  }

  function leerDesde(capitulo: number) {
    desplazarA(capitulo > 0 ? `capitulo-${capitulo}` : "lector");
  }

  const buscarTextoNuevo = (
    <button type="button" onClick={() => setVuelta((v) => v + 1)} disabled={consulta.estado === "cargando"}>
      {consulta.estado === "cargando" ? "Buscando…" : "Buscar texto nuevo"}
    </button>
  );

  return (
    <>
      <Cabecera pantalla="Lectura" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina lectura">
        <Portada
          ficha={ficha}
          capitulos={capitulos.length}
          palabras={palabras}
          minutos={minutosDeLectura(palabras)}
          continuar={continuar}
          alLeer={leerDesde}
          acciones={
            <>
              <a className="boton" href={enlaceDelPdf(idObra, manuscrito.version)} download>
                <Icono nombre="descarga" />
                Descargar PDF
              </a>
              {hechos.length > 0 && (
                <button type="button" onClick={() => desplazarA("personajes-y-lugares")}>
                  <Icono nombre="personas" />
                  Personajes
                </button>
              )}
              {enProduccion && capitulos.length > 0 && buscarTextoNuevo}
            </>
          }
          version={
            <div className="portada__version">
              <p className="lectura__version" aria-live="polite">
                Versión {manuscrito.version}
                {manuscrito.publicada ? " · publicada" : " · sin publicar"}
              </p>
              {versiones.length > 1 && (
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
              )}
            </div>
          }
        />

        {consulta.estado === "fallo" && <AvisoDeFallo fallo={consulta.fallo} reintentar={consulta.reintentar} />}

        <Biblia idObra={idObra} hechos={hechos} alIr={(capitulo) => desplazarA(`capitulo-${capitulo}`)} />

        {capitulos.length === 0 ? (
          <div className="lectura__vacia">
            <Icono nombre="pluma" tamano={28} />
            <p>Aún no hay ningún capítulo aceptado. Aparecerá aquí en cuanto se cierre el primero.</p>
            <div className="lectura__vacia-acciones">
              {buscarTextoNuevo}
              <Link to={enlaceAlAvance}>Ver el avance</Link>
            </div>
          </div>
        ) : (
          <Lector
            idObra={idObra}
            capitulos={capitulos}
            cambiados={cambiados}
            base={leida?.base}
            para={ficha.destinatario}
            dedicatoria={ficha.dedicatoria}
            enlaceDelPdf={enlaceDelPdf(idObra, manuscrito.version)}
            alVolverALaPortada={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          />
        )}

      </main>
    </>
  );
}
