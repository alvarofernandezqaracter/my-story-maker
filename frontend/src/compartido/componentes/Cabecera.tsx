import { Link, NavLink } from "react-router";

// La barra fija de todas las pantallas (SPEC2 RF-84): la marca, el taller y el
// encargo de una obra nueva. `pantalla` dice dónde se está, para quien no mira
// el lateral.
export function Cabecera({ pantalla }: { pantalla: string }) {
  return (
    <header className="cabecera">
      <Link to="/" className="cabecera__marca" aria-label="Ir al taller">
        <img src="/logo.svg" alt="Qaracter" className="cabecera__logo" />
        <span className="cabecera__producto">my-story-maker</span>
      </Link>
      <nav className="cabecera__nav" aria-label="Principal">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "cabecera__enlace activa" : "cabecera__enlace")}>
          Taller
        </NavLink>
      </nav>
      <span className="cabecera__pantalla">{pantalla}</span>
      <NavLink
        to="/encargo"
        className={({ isActive }) => (isActive ? "cabecera__nueva activa" : "cabecera__nueva")}
      >
        + Nueva obra
      </NavLink>
    </header>
  );
}
