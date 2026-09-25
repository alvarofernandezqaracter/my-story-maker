import { useState, type CSSProperties, type FormEvent } from "react";
import { Link } from "react-router";
import { cambiarHecho } from "../../compartido/api/cliente";
import type { Fallo } from "../../compartido/api/fallos";
import type { HechoDeLaBiblia, VersionAbierta } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Icono, type NombreDeIcono } from "../../compartido/componentes/Icono";
import { agruparPorTipo } from "./agrupar";

// Cómo se llama en pantalla cada grupo. Un tipo que el servidor añada y no esté
// aquí sale con su nombre tal cual: no se amplía ni se agrupa con otro (RD-03).
const TITULO_DEL_GRUPO: Record<string, string> = {
  Personaje: "Personajes",
  Lugar: "Lugares",
  Objeto: "Objetos",
  Faccion: "Facciones",
  Evento: "Eventos",
};

const ICONO_DEL_GRUPO: Record<string, NombreDeIcono> = {
  Personaje: "personas",
  Lugar: "lugar",
  Objeto: "objeto",
  Faccion: "bandera",
  Evento: "chispa",
};

// La licencia de cada hecho, con nombre legible. Uno que no esté aquí sale tal cual.
const LICENCIA: Record<string, string> = {
  canon: "Histórico",
  plausible: "Verosímil",
  personal: "Del destinatario",
};

function iniciales(nombre: string): string {
  const palabras = nombre
    .split(/\s+/)
    .filter((p) => p.length > 2 && p[0] === p[0]!.toUpperCase());
  const elegidas = (palabras.length ? palabras : nombre.split(/\s+/)).slice(0, 2);
  return elegidas.map((p) => p[0]!.toUpperCase()).join("");
}

function tono(texto: string): number {
  let h = 0;
  for (let i = 0; i < texto.length; i++) h = (h * 31 + texto.charCodeAt(i)) % 360;
  return h;
}

// La ficha de personajes y lugares: cada hecho de la biblia de la versión leída
// con un enlace a cada capítulo en que se usa (SPEC2 RF-71). Qué capítulos son
// lo dice el servidor. Desde aquí el lector pide cambiar un nombre (RF-76).
export function Biblia({ idObra, hechos, alIr }: { idObra: string; hechos: HechoDeLaBiblia[]; alIr: (capitulo: number) => void }) {
  const grupos = agruparPorTipo(hechos);
  return (
    <section className="biblia" id="personajes-y-lugares" aria-labelledby="biblia-titulo">
      <header className="biblia__cabecera">
        <span className="seccion__antetitulo">Dramatis personae</span>
        <h2 id="biblia-titulo">Personajes y lugares</h2>
        <p className="biblia__entradilla">
          Quién es quién y dónde ocurre. Pulsa un capítulo para saltar a él.
        </p>
      </header>
      {grupos.length === 0 ? (
        <p className="biblia__vacia">La biblia de esta versión todavía no tiene fichas.</p>
      ) : (
        <div className="biblia__grupos">
          {grupos.map((grupo) => (
            <section key={grupo.tipo} className="biblia__grupo" aria-label={TITULO_DEL_GRUPO[grupo.tipo] ?? grupo.tipo}>
              <h3>
                <Icono nombre={ICONO_DEL_GRUPO[grupo.tipo] ?? "chispa"} tamano={16} />
                {TITULO_DEL_GRUPO[grupo.tipo] ?? grupo.tipo}
                <span className="biblia__cuenta">{grupo.hechos.length}</span>
              </h3>
              <ul>
                {grupo.hechos.map((hecho) => (
                  <Hecho key={hecho.id} idObra={idObra} hecho={hecho} alIr={alIr} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

type Envio =
  | { estado: "quieto" }
  | { estado: "enviando" }
  | { estado: "hecho"; version: VersionAbierta }
  | { estado: "fallo"; fallo: Fallo };

function Hecho({ idObra, hecho, alIr }: { idObra: string; hecho: HechoDeLaBiblia; alIr: (capitulo: number) => void }) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState("");
  const [envio, setEnvio] = useState<Envio>({ estado: "quieto" });
  const nombre = hecho.nombre ?? hecho.id;
  const licencia = hecho.licencia ? (LICENCIA[hecho.licencia] ?? hecho.licencia) : null;

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setEnvio({ estado: "enviando" });
    const resultado = await cambiarHecho(idObra, hecho.id, valor);
    setEnvio(resultado.ok ? { estado: "hecho", version: resultado.datos } : { estado: "fallo", fallo: resultado.fallo });
  }

  return (
    <li className="hecho" data-hecho={hecho.id} data-tipo={hecho.tipo}>
      <div className="hecho__cabeza">
        <span className="hecho__avatar" style={{ "--tono": tono(nombre) } as CSSProperties} aria-hidden="true">
          {iniciales(nombre)}
        </span>
        <span className="hecho__identidad">
          <span className="hecho__nombre">{nombre}</span>
          {licencia && (
            <span className="hecho__licencia" data-licencia={hecho.licencia}>
              {licencia}
            </span>
          )}
        </span>
      </div>
      {hecho.capitulos.length === 0 ? (
        <p className="hecho__sin-uso">No aparece en ningún capítulo.</p>
      ) : (
        <nav className="hecho__capitulos" aria-label={`Capítulos de ${nombre}`}>
          {hecho.capitulos.map((capitulo) => (
            <a
              key={capitulo}
              href={`#capitulo-${capitulo}`}
              onClick={(e) => {
                e.preventDefault();
                alIr(capitulo);
              }}
            >
              {capitulo}
            </a>
          ))}
        </nav>
      )}
      {!editando && envio.estado !== "hecho" && (
        <button type="button" className="hecho__cambiar discreto" onClick={() => setEditando(true)}>
          Cambiar el nombre
        </button>
      )}
      {editando && envio.estado !== "hecho" && (
        <form className="hecho__formulario" onSubmit={enviar} aria-label={`Cambiar el nombre de ${nombre}`}>
          <label>
            Nombre nuevo
            <input value={valor} onChange={(e) => setValor(e.target.value)} placeholder={nombre} autoFocus />
          </label>
          <p className="hecho__advertencia">Se escribirá una versión nueva con los capítulos donde aparece.</p>
          <div className="hecho__botones">
            <button type="submit" className="principal" disabled={envio.estado === "enviando"}>
              {envio.estado === "enviando" ? "Pidiendo…" : "Pedir el cambio"}
            </button>
            <button type="button" onClick={() => setEditando(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}
      {envio.estado === "fallo" && <AvisoDeFallo fallo={envio.fallo} />}
      {envio.estado === "hecho" && (
        <p className="hecho__aviso" role="status">
          Nace la versión {envio.version.version}: se reescribirán{" "}
          {envio.version.capitulos_cambiados.length === 1 ? "el capítulo " : "los capítulos "}
          {envio.version.capitulos_cambiados.join(", ")}.{" "}
          <Link to={`/obras/${encodeURIComponent(idObra)}`}>Ver el avance</Link>
        </p>
      )}
    </li>
  );
}
