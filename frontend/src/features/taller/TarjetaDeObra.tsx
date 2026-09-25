import { Link } from "react-router";
import type { ObraDelTaller } from "../../compartido/api/tipos";
import { Libro } from "../../compartido/componentes/Libro";
import { ETIQUETA_DE_SITUACION } from "../../compartido/situacion";

// Una obra en el taller (SPEC2 RF-81). Todo sale tal cual del listado: la
// interfaz no cuenta ni deduce nada, solo lo pinta.
export function TarjetaDeObra({ obra }: { obra: ObraDelTaller }) {
  const cerrados = obra.capitulos_cerrados;
  const objetivo = obra.capitulos_objetivo;
  const fraccion = objetivo > 0 ? Math.min(1, cerrados / objetivo) : 0;
  return (
    <Link
      to={`/obras/${encodeURIComponent(obra.id_obra)}`}
      className="tarjeta-de-obra"
      data-situacion={obra.situacion}
      aria-label={`${obra.titulo}, ${ETIQUETA_DE_SITUACION[obra.situacion]}`}
    >
      <span className="tarjeta-de-obra__cabeza">
        <Libro titulo={obra.titulo} tamano="mini" />
        <span className="tarjeta-de-obra__identidad">
          <strong className="tarjeta-de-obra__titulo">{obra.titulo}</strong>
          <span className="tarjeta-de-obra__epoca">{obra.epoca}</span>
          {obra.destinatario && <span className="tarjeta-de-obra__para">Para {obra.destinatario}</span>}
        </span>
      </span>

      <span className="tarjeta-de-obra__progreso">
        <span className="tarjeta-de-obra__fila">
          <span>Capítulos</span>
          <span>
            {cerrados} / {objetivo}
          </span>
        </span>
        <span
          className="barra"
          role="progressbar"
          aria-label={`Capítulos cerrados de ${obra.titulo}`}
          aria-valuemin={0}
          aria-valuemax={objetivo}
          aria-valuenow={cerrados}
        >
          <span className="barra__relleno" style={{ width: `${fraccion * 100}%` }} />
        </span>
      </span>

      {obra.situacion === "detenida" && obra.motivo_de_la_detencion && (
        <span className="tarjeta-de-obra__alerta">{obra.motivo_de_la_detencion}</span>
      )}

      <span className="tarjeta-de-obra__pie">
        <span className="situacion" data-situacion={obra.situacion}>
          {ETIQUETA_DE_SITUACION[obra.situacion]}
        </span>
        <span>
          v{obra.version_en_curso}
          {obra.version_publicada !== null && ` · publicada la v${obra.version_publicada}`}
        </span>
      </span>
    </Link>
  );
}
