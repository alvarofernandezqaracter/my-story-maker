import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { cambiarHecho } from "../../compartido/api/cliente";
import type { Fallo } from "../../compartido/api/fallos";
import type { HechoDeLaBiblia, VersionAbierta } from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
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

// La ficha de personajes y lugares: cada hecho de la biblia de la versión leída
// con un enlace a cada capítulo en que se usa (SPEC2 RF-71). Qué capítulos son
// lo dice el servidor. Desde aquí el lector pide cambiar un nombre (RF-76).
export function Biblia({ idObra, hechos }: { idObra: string; hechos: HechoDeLaBiblia[] }) {
  const grupos = agruparPorTipo(hechos);
  return (
    <details className="biblia" open>
      <summary>Personajes y lugares</summary>
      {grupos.length === 0 ? (
        <p className="biblia__vacia">La biblia de esta versión todavía no tiene fichas.</p>
      ) : (
        <div className="biblia__grupos">
          {grupos.map((grupo) => (
            <section key={grupo.tipo} className="biblia__grupo" aria-label={TITULO_DEL_GRUPO[grupo.tipo] ?? grupo.tipo}>
              <h2>{TITULO_DEL_GRUPO[grupo.tipo] ?? grupo.tipo}</h2>
              <ul>
                {grupo.hechos.map((hecho) => (
                  <Hecho key={hecho.id} idObra={idObra} hecho={hecho} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </details>
  );
}

type Envio =
  | { estado: "quieto" }
  | { estado: "enviando" }
  | { estado: "hecho"; version: VersionAbierta }
  | { estado: "fallo"; fallo: Fallo };

function Hecho({ idObra, hecho }: { idObra: string; hecho: HechoDeLaBiblia }) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState("");
  const [envio, setEnvio] = useState<Envio>({ estado: "quieto" });
  const nombre = hecho.nombre ?? hecho.id;

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setEnvio({ estado: "enviando" });
    const resultado = await cambiarHecho(idObra, hecho.id, valor);
    setEnvio(resultado.ok ? { estado: "hecho", version: resultado.datos } : { estado: "fallo", fallo: resultado.fallo });
  }

  return (
    <li className="hecho" data-hecho={hecho.id}>
      <div className="hecho__cabeza">
        <span className="hecho__nombre">{nombre}</span>
        {hecho.licencia && <span className="hecho__licencia">{hecho.licencia}</span>}
      </div>
      {hecho.capitulos.length === 0 ? (
        <p className="hecho__sin-uso">No aparece en ningún capítulo.</p>
      ) : (
        <nav className="hecho__capitulos" aria-label={`Capítulos de ${nombre}`}>
          {hecho.capitulos.map((capitulo) => (
            <a key={capitulo} href={`#capitulo-${capitulo}`}>
              Cap. {capitulo}
            </a>
          ))}
        </nav>
      )}
      {!editando && envio.estado !== "hecho" && (
        <button type="button" className="hecho__cambiar" onClick={() => setEditando(true)}>
          Cambiar el nombre
        </button>
      )}
      {editando && envio.estado !== "hecho" && (
        <form className="hecho__formulario" onSubmit={enviar} aria-label={`Cambiar el nombre de ${nombre}`}>
          <label>
            Nombre nuevo
            <input value={valor} onChange={(e) => setValor(e.target.value)} placeholder={nombre} />
          </label>
          <button type="submit" disabled={envio.estado === "enviando"}>
            {envio.estado === "enviando" ? "Pidiendo…" : "Pedir el cambio"}
          </button>
          <button type="button" onClick={() => setEditando(false)}>
            Cancelar
          </button>
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
