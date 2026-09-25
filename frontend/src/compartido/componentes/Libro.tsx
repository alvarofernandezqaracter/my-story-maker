import type { CSSProperties } from "react";

// La cubierta de una obra, dibujada a partir de su título: la misma obra sale
// siempre con la misma paleta y el mismo ornamento. Es decoración, no dato.

type Paleta = { fondo: string; fondo2: string; tinta: string; oro: string };

const PALETAS: Paleta[] = [
  { fondo: "#1f3140", fondo2: "#2f4a5f", tinta: "#f6efe3", oro: "#ff9a55" },
  { fondo: "#5a1f24", fondo2: "#7a2e31", tinta: "#f7ecdc", oro: "#e3b567" },
  { fondo: "#1f3b33", fondo2: "#2e5749", tinta: "#f1ecdd", oro: "#d9b36a" },
  { fondo: "#2a2344", fondo2: "#3e3565", tinta: "#f3eee6", oro: "#f0a868" },
  { fondo: "#8a3b18", fondo2: "#b0532a", tinta: "#fbf1e4", oro: "#ffd9a8" },
  { fondo: "#26303a", fondo2: "#3a4856", tinta: "#f4efe8", oro: "#ff7932" },
];

function huella(texto: string): number {
  let h = 2166136261;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function paletaDe(titulo: string): Paleta {
  return PALETAS[huella(titulo) % PALETAS.length]!;
}

type Props = {
  titulo: string;
  subtitulo?: string | null;
  autor?: string | null;
  tamano?: "mini" | "media" | "grande";
  className?: string;
};

export function Libro({ titulo, subtitulo, autor, tamano = "media", className }: Props) {
  const paleta = paletaDe(titulo);
  const motivo = huella(titulo + "#") % 3;
  const estilo = {
    "--libro-fondo": paleta.fondo,
    "--libro-fondo-2": paleta.fondo2,
    "--libro-tinta": paleta.tinta,
    "--libro-oro": paleta.oro,
  } as CSSProperties;
  return (
    <div className={`libro libro--${tamano}${className ? ` ${className}` : ""}`} style={estilo} aria-hidden="true">
      <div className="libro__cubierta">
        {tamano !== "mini" && (
          <svg className="libro__ornamento" viewBox="0 0 200 300" preserveAspectRatio="none">
            <rect x="10" y="10" width="180" height="280" fill="none" stroke="currentColor" strokeWidth="1" />
            <rect x="16" y="16" width="168" height="268" fill="none" stroke="currentColor" strokeWidth="0.5" />
            {motivo === 0 && (
              <g fill="none" stroke="currentColor" strokeWidth="0.8">
                <path d="M100 228 l14 14 -14 14 -14 -14z" />
                <path d="M100 236 l6 6 -6 6 -6 -6z" />
                <path d="M60 242 h26 M114 242 h26" />
              </g>
            )}
            {motivo === 1 && (
              <g fill="none" stroke="currentColor" strokeWidth="0.8">
                <circle cx="100" cy="242" r="14" />
                <circle cx="100" cy="242" r="8" />
                <path d="M56 242 h30 M114 242 h30" />
              </g>
            )}
            {motivo === 2 && (
              <g fill="none" stroke="currentColor" strokeWidth="0.8">
                <path d="M100 226 c10 8 10 24 0 32 c-10 -8 -10 -24 0 -32z" />
                <path d="M58 242 q21 -10 30 0 M112 242 q9 -10 30 0" />
              </g>
            )}
            <g fill="currentColor">
              <circle cx="30" cy="30" r="1.6" />
              <circle cx="170" cy="30" r="1.6" />
              <circle cx="30" cy="270" r="1.6" />
              <circle cx="170" cy="270" r="1.6" />
            </g>
          </svg>
        )}
        {tamano !== "mini" && (
          <div className="libro__texto">
            {subtitulo && <span className="libro__subtitulo">{subtitulo}</span>}
            <span className="libro__titulo">{titulo}</span>
            <span className="libro__filete" />
            {autor && <span className="libro__autor">{autor}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
