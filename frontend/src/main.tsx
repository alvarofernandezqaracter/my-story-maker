import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./compartido/estilos/tokens.css";
import "./compartido/estilos/base.css";
import { Rutas } from "./rutas";

const raiz = document.getElementById("root");
if (raiz === null) throw new Error("Falta el elemento #root en index.html");

createRoot(raiz).render(
  <StrictMode>
    <BrowserRouter>
      <Rutas />
    </BrowserRouter>
  </StrictMode>,
);
