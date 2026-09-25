import type { ReactNode } from "react";
import type { FichaDeObra } from "../../compartido/api/tipos";
import { Icono } from "../../compartido/componentes/Icono";
import { Libro } from "../../compartido/componentes/Libro";
import { duracion, miles, romano } from "./herramientas";

type Props = {
  ficha: FichaDeObra;
  capitulos: number;
  palabras: number;
  minutos: number;
  /** El capítulo en que el lector se quedó, si no es el primero. */
  continuar: number | null;
  alLeer: (capitulo: number) => void;
  acciones: ReactNode;
  version: ReactNode;
};

// La portada: título, para quién y la dedicatoria, tal como vienen en la ficha
// (SPEC2 RF-70), junto a la cubierta del libro y lo que se tarda en leerlo. Sin
// destinatario, solo el título.
export function Portada({ ficha, capitulos, palabras, minutos, continuar, alLeer, acciones, version }: Props) {
  return (
    <div className="portada-envoltorio">
      <div className="portada__fondo" aria-hidden="true" />
      <div className="portada__escena">
        <Libro titulo={ficha.titulo} subtitulo={ficha.epoca} autor="Story Maker" tamano="grande" className="portada__libro" />
        <section className="portada" aria-label="Portada">
          <span className="portada__genero">
            <Icono nombre="chispa" tamano={14} /> Novela histórica · {ficha.epoca}
          </span>
          <h1 className="portada__titulo">{ficha.titulo}</h1>
          {ficha.destinatario && <p className="portada__para">Para {ficha.destinatario}</p>}
          {ficha.dedicatoria && (
            <blockquote className="portada__dedicatoria" aria-label="Dedicatoria">
              {ficha.dedicatoria}
            </blockquote>
          )}
          {capitulos > 0 && (
            <ul className="portada__datos" aria-label="La obra en cifras">
              <li>
                <strong>{capitulos}</strong> {capitulos === 1 ? "capítulo" : "capítulos"}
              </li>
              <li>
                <strong>{miles(palabras)}</strong> palabras
              </li>
              <li>
                <Icono nombre="reloj" tamano={15} /> <strong>{duracion(minutos)}</strong> de lectura
              </li>
            </ul>
          )}
          <div className="portada__acciones">
            {capitulos > 0 && (
              <button type="button" className="principal portada__leer" onClick={() => alLeer(continuar ?? 0)}>
                <Icono nombre="libro" />
                {continuar ? `Continuar en el capítulo ${romano(continuar)}` : "Empezar a leer"}
              </button>
            )}
            {continuar !== null && capitulos > 0 && (
              <button type="button" onClick={() => alLeer(0)}>
                Desde el principio
              </button>
            )}
            {acciones}
          </div>
          {version}
        </section>
      </div>
    </div>
  );
}
