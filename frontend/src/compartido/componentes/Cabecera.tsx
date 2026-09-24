import { Link } from "react-router";

export function Cabecera({ pantalla }: { pantalla: string }) {
  return (
    <header className="cabecera">
      <Link to="/" className="cabecera__marca" aria-label="Volver al encargo">
        <img src="/logo.svg" alt="Qaracter" className="cabecera__logo" />
      </Link>
      <span className="cabecera__producto">my-story-maker</span>
      <span className="cabecera__pantalla">{pantalla}</span>
    </header>
  );
}
