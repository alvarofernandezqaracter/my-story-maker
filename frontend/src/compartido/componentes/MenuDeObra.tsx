import { NavLink } from "react-router";
import { verObra } from "../api/cliente";
import { ETIQUETA_DE_SITUACION } from "../situacion";
import { useConsulta } from "../usar-consulta";

export type PantallaDeObra = "avance" | "tareas" | "lectura" | "versiones";

const PESTANAS: { pantalla: PantallaDeObra; etiqueta: string; sufijo: string }[] = [
  { pantalla: "avance", etiqueta: "Avance", sufijo: "" },
  { pantalla: "tareas", etiqueta: "Tareas", sufijo: "/tareas" },
  { pantalla: "lectura", etiqueta: "Lectura", sufijo: "/manuscrito" },
  { pantalla: "versiones", etiqueta: "Versiones", sufijo: "/versiones" },
];

// El lateral de las pantallas de una obra, al estilo de un gestor de proyectos
// (SPEC2 RF-30): arriba la obra y su situación tal como la sirve el servidor, y
// debajo las pantallas, que saltan con un clic y marcan en cuál se está. Cada
// una es una dirección, así que también se puede abrir en otra pestaña.
export function MenuDeObra({ idObra }: { idObra: string }) {
  const base = `/obras/${encodeURIComponent(idObra)}`;
  const ficha = useConsulta(() => verObra(idObra), `lateral:${idObra}`);
  const datos = ficha.datos;
  return (
    <aside className="lateral">
      <div className="lateral__obra">
        <span className="lateral__titulo">{datos?.titulo ?? "Obra"}</span>
        <span className="lateral__id ruta">{idObra}</span>
        {datos && (
          <span className="situacion" data-situacion={datos.situacion}>
            {ETIQUETA_DE_SITUACION[datos.situacion]}
          </span>
        )}
      </div>
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
    </aside>
  );
}
