import { NavLink } from "react-router";
import { verObra } from "../api/cliente";
import { ETIQUETA_DE_SITUACION } from "../situacion";
import { useConsulta } from "../usar-consulta";
import { Icono, type NombreDeIcono } from "./Icono";
import { Libro } from "./Libro";

export type PantallaDeObra = "avance" | "tareas" | "lectura" | "versiones";

const PESTANAS: { pantalla: PantallaDeObra; etiqueta: string; sufijo: string; icono: NombreDeIcono }[] = [
  { pantalla: "lectura", etiqueta: "Lectura", sufijo: "/manuscrito", icono: "libro" },
  { pantalla: "avance", etiqueta: "Avance", sufijo: "", icono: "actividad" },
  { pantalla: "tareas", etiqueta: "Tareas", sufijo: "/tareas", icono: "tareas" },
  { pantalla: "versiones", etiqueta: "Versiones", sufijo: "/versiones", icono: "versiones" },
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
        {datos && <Libro titulo={datos.titulo} tamano="mini" className="lateral__libro" />}
        <div className="lateral__datos">
          <span className="lateral__titulo">{datos?.titulo ?? "Obra"}</span>
          {datos && <span className="lateral__epoca">{datos.epoca}</span>}
          {datos && (
            <span className="situacion" data-situacion={datos.situacion}>
              {ETIQUETA_DE_SITUACION[datos.situacion]}
            </span>
          )}
        </div>
      </div>
      <nav className="menu-de-obra" aria-label="Pantallas de la obra">
        {PESTANAS.map(({ pantalla, etiqueta, sufijo, icono }) => (
          <NavLink
            key={pantalla}
            to={base + sufijo}
            end
            className={({ isActive }) => (isActive ? "menu-de-obra__pestana activa" : "menu-de-obra__pestana")}
          >
            <Icono nombre={icono} tamano={17} />
            {etiqueta}
          </NavLink>
        ))}
      </nav>
      <span className="lateral__id ruta">{idObra}</span>
    </aside>
  );
}
