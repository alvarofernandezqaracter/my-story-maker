import { Link, Route, Routes } from "react-router";
import { Cabecera } from "./compartido/componentes/Cabecera";
import { PantallaDelAvance } from "./features/avance/PantallaDelAvance";
import { PantallaDelEncargo } from "./features/encargo/PantallaDelEncargo";
import { PantallaDelManuscrito } from "./features/manuscrito/PantallaDelManuscrito";

export function Rutas() {
  return (
    <Routes>
      <Route path="/" element={<PantallaDelEncargo />} />
      <Route path="/obras/:idObra" element={<PantallaDelAvance />} />
      <Route path="/obras/:idObra/manuscrito" element={<PantallaDelManuscrito />} />
      <Route path="*" element={<NoExiste />} />
    </Routes>
  );
}

function NoExiste() {
  return (
    <>
      <Cabecera pantalla="Dirección desconocida" />
      <main className="pagina">
        <h1>Esta dirección no existe</h1>
        <p>
          <Link to="/">Ir al encargo</Link>
        </p>
      </main>
    </>
  );
}
