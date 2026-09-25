import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "@fontsource-variable/inter";
import "@fontsource-variable/literata/opsz.css";
import "@fontsource-variable/literata/opsz-italic.css";
import "@fontsource-variable/fraunces";
import "./compartido/estilos/tokens.css";
import "./compartido/estilos/base.css";
import { aplicarTema, temaGuardado } from "./compartido/preferencias";
import { Rutas } from "./rutas";

const raiz = document.getElementById("root");
if (raiz === null) throw new Error("Falta el elemento #root en index.html");

aplicarTema(temaGuardado());

createRoot(raiz).render(
  <StrictMode>
    <BrowserRouter>
      <Rutas />
    </BrowserRouter>
  </StrictMode>,
);
