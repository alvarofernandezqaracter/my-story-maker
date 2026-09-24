import { NavLink } from "react-router";

export type PantallaDeObra = "avance" | "tareas" | "lectura";

const PESTANAS: { pantalla: PantallaDeObra; etiqueta: string; sufijo: string }[] = [
  { pantalla: "avance", etiqueta: "Avance", sufijo: "" },
  { pantalla: "tareas", etiqueta: "Tareas", sufijo: "/tareas" },
  { pantalla: "lectura", etiqueta: "Lectura", sufijo: "/manuscrito" },
];

// El mismo menú en las tres pantallas de una obra: salta con un clic y marca en
// cuál se está (SPEC2 RF-30). Cada pestaña es una dirección, así que también se
// puede abrir en otra pestaña del navegador.
export function MenuDeObra({ idObra }: { idObra: string }) {
  const base = `/obras/${encodeURIComponent(idObra)}`;
  return (
    <nav className="menu-de-obra" aria-label="Pantallas de la obra">
      {PESTANAS.map(({ pantalla, etiqueta, sufijo }) => (
        <NavLink
          key={pantalla}
          to={base + sufijo}
          end
          className={({ isActive }) => (isActive ? "menu-de-obra__pestana activa" : "menu-de-obra__pestana")}
        >
          {etiqueta}
        </NavLink>
      ))}
    </nav>
  );
}
