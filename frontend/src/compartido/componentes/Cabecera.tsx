import { Link, NavLink } from "react-router";
import { TEMAS, aplicarTema, esUnoDe, usePreferencia, type Tema } from "../preferencias";
import { Icono } from "./Icono";

const SIGUIENTE: Record<Tema, Tema> = { sistema: "oscuro", oscuro: "claro", claro: "sistema" };
const NOMBRE_DEL_TEMA: Record<Tema, string> = {
  sistema: "Tema del sistema",
  oscuro: "Tema oscuro",
  claro: "Tema claro",
};

// La barra fija de todas las pantallas (SPEC2 RF-84): la marca, el taller y el
// encargo de una obra nueva. `pantalla` dice dónde se está, para quien no mira
// el lateral.
export function Cabecera({ pantalla }: { pantalla: string }) {
  const [tema, setTema] = usePreferencia<Tema>("tema", "sistema", esUnoDe(TEMAS));

  function cambiarTema() {
    const siguiente = SIGUIENTE[tema];
    setTema(siguiente);
    aplicarTema(siguiente);
  }

  return (
    <header className="cabecera">
      <Link to="/" className="cabecera__marca" aria-label="Ir al taller">
        <img src="/logo.svg" alt="Qaracter" className="cabecera__logo cabecera__logo--sobre-claro" />
        <img src="/logo-claro.svg" alt="" aria-hidden="true" className="cabecera__logo cabecera__logo--sobre-oscuro" />
        <span className="cabecera__separador" aria-hidden="true" />
        <span className="cabecera__producto">
          Story Maker
          <span className="cabecera__lema">Novelas históricas a medida</span>
        </span>
      </Link>
      <nav className="cabecera__nav" aria-label="Principal">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "cabecera__enlace activa" : "cabecera__enlace")}>
          <Icono nombre="tablero" tamano={16} />
          Taller
        </NavLink>
      </nav>
      <span className="cabecera__pantalla">{pantalla}</span>
      <div className="cabecera__derecha">
        <button
          type="button"
          className="cabecera__tema"
          onClick={cambiarTema}
          aria-label={`${NOMBRE_DEL_TEMA[tema]}. Cambiar`}
          title={NOMBRE_DEL_TEMA[tema]}
        >
          <Icono nombre={tema === "oscuro" ? "luna" : tema === "claro" ? "sol" : "capas"} tamano={17} />
        </button>
        <NavLink
          to="/encargo"
          className={({ isActive }) => (isActive ? "cabecera__nueva activa" : "cabecera__nueva")}
        >
          <Icono nombre="pluma" tamano={16} />
          <span className="cabecera__nueva-texto">Nueva obra</span>
        </NavLink>
      </div>
    </header>
  );
}
