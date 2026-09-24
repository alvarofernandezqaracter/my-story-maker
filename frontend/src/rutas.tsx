import { Link, Route, Routes } from "react-router";
import { Cabecera } from "./compartido/componentes/Cabecera";
import { PantallaDelAvance } from "./features/avance/PantallaDelAvance";
import { PantallaDelEncargo } from "./features/encargo/PantallaDelEncargo";
import { PantallaDelManuscrito } from "./features/manuscrito/PantallaDelManuscrito";
import { PantallaDelTaller } from "./features/taller/PantallaDelTaller";
import { PantallaDeTareas } from "./features/tareas/PantallaDeTareas";
import { PantallaDeVersiones } from "./features/versiones/PantallaDeVersiones";

export function Rutas() {
  return (
    <Routes>
      <Route path="/" element={<PantallaDelTaller />} />
      <Route path="/encargo" element={<PantallaDelEncargo />} />
      <Route path="/obras/:idObra" element={<PantallaDelAvance />} />
      <Route path="/obras/:idObra/tareas" element={<PantallaDeTareas />} />
      <Route path="/obras/:idObra/manuscrito" element={<PantallaDelManuscrito />} />
      <Route path="/obras/:idObra/versiones" element={<PantallaDeVersiones />} />
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
          <Link to="/">Ir al taller</Link>
        </p>
      </main>
    </>
  );
}
