import type { FichaDeObra } from "../../compartido/api/tipos";

// La portada: título, para quién y la dedicatoria, tal como vienen en la ficha
// (SPEC2 RF-70). Sin destinatario, solo el título.
export function Portada({ ficha }: { ficha: FichaDeObra }) {
  return (
    <section className="portada" aria-label="Portada">
      <h1 className="portada__titulo">{ficha.titulo}</h1>
      {ficha.destinatario && <p className="portada__para">Para {ficha.destinatario}</p>}
      {ficha.dedicatoria && (
        <blockquote className="portada__dedicatoria" aria-label="Dedicatoria">
          {ficha.dedicatoria}
        </blockquote>
      )}
    </section>
  );
}
