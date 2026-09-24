import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";
import type { TrazaServida } from "../src/compartido/api/tipos";
import { PantallaDelAvance } from "../src/features/avance/PantallaDelAvance";
import { PantallaDelManuscrito } from "../src/features/manuscrito/PantallaDelManuscrito";
import { PantallaDeTareas } from "../src/features/tareas/PantallaDeTareas";
import { EventSourceFalso } from "./EventSourceFalso";
import { API, ID_OBRA, servidor, sinServidor, traza } from "./servidor";

function montar(ruta = `/obras/${ID_OBRA}/tareas`) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/obras/:idObra" element={<PantallaDelAvance />} />
        <Route path="/obras/:idObra/tareas" element={<PantallaDeTareas />} />
        <Route path="/obras/:idObra/manuscrito" element={<PantallaDelManuscrito />} />
      </Routes>
    </MemoryRouter>,
  );
}

const pasa = {
  final: [
    { gancho: "forma", pasa: true, motivos: [] },
    { gancho: "policy", pasa: true, motivos: [] },
  ],
};
const noPasa = {
  final: [
    { gancho: "forma", pasa: true, motivos: [] },
    { gancho: "policy", pasa: false, motivos: ["vetado"] },
  ],
};

beforeEach(() => {
  EventSourceFalso.reiniciar();
  vi.stubGlobal("EventSource", EventSourceFalso);
});
afterEach(() => vi.unstubAllGlobals());

describe("las tareas hechas (SPEC2 RF-26, RF-27)", () => {
  it("agrupa por capítulo en el orden servido y enseña rol, tarea, escena, duración y hooks", async () => {
    servidor.use(
      http.get(`${API}/obras/:id/trazas`, () =>
        HttpResponse.json([
          traza({
            id: "a",
            capitulo: null,
            escena: null,
            rol: "constructor_de_mundo",
            tarea: "poblar_mundo",
            latencia_ms: 95000,
          }),
          traza({ id: "b", capitulo: 1, ganchos: pasa }),
          traza({ id: "c", capitulo: 1, escena: "e2", ganchos: noPasa }),
          traza({
            id: "d",
            capitulo: 2,
            rol: "planificador",
            tarea: "planificar",
            cerrada_en: null,
            latencia_ms: null,
          }),
        ]),
      ),
    );
    montar();
    const grupos = await screen.findAllByRole("region");
    expect(grupos.map((g) => g.getAttribute("aria-label"))).toEqual([
      "De la obra",
      "Capítulo 1",
      "Capítulo 2",
    ]);

    const obra = within(grupos[0]!).getAllByRole("row")[1]!;
    expect(obra).toHaveTextContent("constructor_de_mundo");
    expect(obra).toHaveTextContent("1 min 35 s");

    const [, pasada, fallida] = within(grupos[1]!).getAllByRole("row");
    expect(pasada).toHaveTextContent("42 s");
    expect(pasada).toHaveTextContent("Pasó");
    expect(fallida).toHaveTextContent("No pasó");

    expect(within(grupos[2]!).getByText("En curso")).toBeInTheDocument();
  });

  it("no enseña tokens, coste ni intentos: solo lo esencial (D-09)", async () => {
    montar();
    await screen.findByText("redactar_escena");
    expect(screen.queryByText(/token/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/coste/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/intento/i)).not.toBeInTheDocument();
  });

  it("sin tareas lo dice, y «Actualizar la lista» vuelve a pedirla", async () => {
    const usuario = userEvent.setup();
    let lista: TrazaServida[] = [];
    servidor.use(http.get(`${API}/obras/:id/trazas`, () => HttpResponse.json(lista)));
    montar();
    expect(await screen.findByText(/Todavía no se ha hecho ninguna tarea/)).toBeInTheDocument();
    lista = [traza()];
    await usuario.click(screen.getByRole("button", { name: "Actualizar la lista" }));
    expect(await screen.findByText("redactar_escena")).toBeInTheDocument();
  });

  it("con el servidor caído dice qué pasa; con un 404, el mensaje del servidor", async () => {
    servidor.use(http.get(`${API}/obras/:id/trazas`, sinServidor));
    const primera = montar();
    expect(await screen.findByText(MENSAJE_SIN_SERVIDOR)).toBeInTheDocument();
    primera.unmount();
    servidor.use(
      http.get(`${API}/obras/:id/trazas`, () =>
        HttpResponse.json({ detail: "No hay ninguna obra x" }, { status: 404 }),
      ),
    );
    montar("/obras/x/tareas");
    expect(await screen.findByRole("alert")).toHaveTextContent("No hay ninguna obra x");
  });
});

describe("el menú de la obra (SPEC2 RF-30)", () => {
  it("desde cualquier pantalla se llega a las otras dos con un clic, y marca dónde se está", async () => {
    const usuario = userEvent.setup();
    montar(`/obras/${ID_OBRA}`);
    await screen.findByText("La luz de Triana");
    const menu = () => screen.getByRole("navigation", { name: "Pantallas de la obra" });
    expect(within(menu()).getByRole("link", { name: "Avance" })).toHaveClass("activa");

    await usuario.click(within(menu()).getByRole("link", { name: "Tareas" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Tareas" })).toBeInTheDocument();
    expect(within(menu()).getByRole("link", { name: "Tareas" })).toHaveClass("activa");

    await usuario.click(within(menu()).getByRole("link", { name: "Lectura" }));
    expect(await screen.findByText("Amanecía sobre el río.")).toBeInTheDocument();
    expect(within(menu()).getByRole("link", { name: "Lectura" })).toHaveClass("activa");
    expect(within(menu()).getByRole("link", { name: "Avance" })).not.toHaveClass("activa");

    expect(within(menu()).getByRole("link", { name: "Tareas" })).toHaveAttribute(
      "href",
      `/obras/${ID_OBRA}/tareas`,
    );
  });
});
