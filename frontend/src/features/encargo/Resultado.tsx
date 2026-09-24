import type { PasadaDeEntrevista, TipoDeContradiccion } from "../../compartido/api/tipos";
import { ETIQUETA_DE_CONTRADICCION, etiquetaDe } from "./campos";

type Props = {
  pasada: PasadaDeEntrevista;
  asumidas: TipoDeContradiccion[];
  bloqueado: boolean;
  alAsumir: (tipo: TipoDeContradiccion) => void;
  alDeshacer: (tipo: TipoDeContradiccion) => void;
};

function ListaDeRutas({ titulo, rutas }: { titulo: string; rutas: string[] }) {
  if (rutas.length === 0) return null;
  return (
    <div className="resultado__bloque">
      <h3>{titulo}</h3>
      <ul>
        {rutas.map((ruta) => (
          <li key={ruta}>
            {etiquetaDe(ruta)} <span className="ruta">{ruta}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Lo que contestó el sistema en la última pasada, pintado tal cual llega: aquí
// no se decide qué falta ni qué choca, solo se recorren las listas (SPEC2 RF-03).
export function Resultado({ pasada, asumidas, bloqueado, alAsumir, alDeshacer }: Props) {
  const cuantasDelTipo = (tipo: TipoDeContradiccion) =>
    pasada.contradicciones.filter((c) => c.tipo === tipo).length;
  const descartes = pasada.hechos_descartados.length + pasada.contradicciones_descartadas;
  const nadaQueDecir =
    pasada.faltan.length === 0 &&
    pasada.no_validos.length === 0 &&
    pasada.contradicciones.length === 0;

  return (
    <section className="resultado" aria-label="Lo que ha entendido el sistema">
      <h2 className="resultado__titulo">El Entrevistador · pasada {pasada.numero}</h2>

      <ListaDeRutas titulo="Te falta decirme" rutas={pasada.faltan} />
      <ListaDeRutas titulo="No puedo usar" rutas={pasada.no_validos} />

      {pasada.contradicciones.length > 0 && (
        <div className="resultado__bloque">
          <h3>Cosas que no casan</h3>
          {pasada.contradicciones.map((contradiccion, i) => {
            const asumida = asumidas.includes(contradiccion.tipo);
            return (
              <article
                key={i}
                className={asumida ? "choque choque--asumido" : "choque"}
                data-tipo={contradiccion.tipo}
              >
                <h4>{ETIQUETA_DE_CONTRADICCION[contradiccion.tipo]}</h4>
                <p className="choque__campos">
                  {contradiccion.campos.map((ruta) => (
                    <span key={ruta} className="ruta">
                      {ruta}{" "}
                    </span>
                  ))}
                </p>
                <blockquote className="choque__evidencia">{contradiccion.evidencia}</blockquote>
                {asumida ? (
                  <p className="choque__estado">
                    La das por buena.{" "}
                    <button
                      type="button"
                      className="discreto"
                      disabled={bloqueado}
                      onClick={() => alDeshacer(contradiccion.tipo)}
                    >
                      Deshacer
                    </button>
                  </p>
                ) : (
                  <button
                    type="button"
                    disabled={bloqueado}
                    onClick={() => alAsumir(contradiccion.tipo)}
                  >
                    {cuantasDelTipo(contradiccion.tipo) > 1
                      ? "Darlas por buenas todas las de este tipo"
                      : "Darla por buena"}
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}

      {pasada.hechos.length > 0 && (
        <div className="resultado__bloque">
          <h3>Lo que he sacado de tus textos</h3>
          <ul className="hechos">
            {pasada.hechos.map((hecho, i) => (
              <li key={i}>
                <strong>{etiquetaDe(hecho.campo)}</strong> <span className="ruta">{hecho.campo}</span>
                <blockquote>{hecho.cita}</blockquote>
              </li>
            ))}
          </ul>
        </div>
      )}

      {descartes > 0 && (
        <details className="resultado__descartes">
          <summary>Descartado: {descartes}</summary>
          <p>
            Datos de tus textos descartados: {pasada.hechos_descartados.length}. Posibles choques
            descartados: {pasada.contradicciones_descartadas}.
          </p>
        </details>
      )}

      {nadaQueDecir && <p>No me falta nada ni veo nada que no case.</p>}
    </section>
  );
}
