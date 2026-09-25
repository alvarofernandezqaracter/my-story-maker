import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it } from "vitest";
import { PantallaDelManuscrito } from "../src/features/manuscrito/PantallaDelManuscrito";
import { API, ficha, ID_OBRA, manuscrito, servidor, version } from "./servidor";

function Direccion() {
  const { pathname, search } = useLocation();
  return <output aria-label="dirección">{pathname + search}</output>;
}

function montar(ruta = `/obras/${ID_OBRA}/manuscrito`) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route
          path="/obras/:idObra/manuscrito"
          element={
            <>
              <PantallaDelManuscrito />
              <Direccion />
            </>
          }
        />
        <Route path="/obras/:idObra" element={<p>Pantalla del avance</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("la portada, el índice y la biblia (SPEC2 §4.5)", () => {
  it("RF-70: la portada trae el título, para quién y la dedicatoria tal como vienen", async () => {
    montar();
    const portada = await screen.findByRole("region", { name: "Portada" });
    expect(within(portada).getByRole("heading", { level: 1 })).toHaveTextContent("La luz de Triana");
    expect(within(portada).getByText("Para Lucía")).toBeInTheDocument();
    expect(within(portada).getByLabelText("Dedicatoria")).toHaveTextContent("Para Lucía, que me enseñó a leer");
  });

  it("RF-70: sin destinatario, solo el título", async () => {
    servidor.use(
      http.get(`${API}/obras/:id`, () => HttpResponse.json(ficha({ destinatario: null, dedicatoria: null }))),
    );
    montar();
    const portada = await screen.findByRole("region", { name: "Portada" });
    expect(within(portada).queryByText(/^Para /)).not.toBeInTheDocument();
    expect(within(portada).queryByLabelText("Dedicatoria")).not.toBeInTheDocument();
  });

  it("RF-70: el índice marca los capítulos que la versión leída cambió respecto de su base", async () => {
    servidor.use(
      http.get(`${API}/obras/:id/manuscrito`, () => HttpResponse.json(manuscrito({ version: 2 }))),
      http.get(`${API}/obras/:id/versiones`, () =>
        HttpResponse.json([version(), version({ numero: 2, base: 1, capitulos_cambiados: [2] })]),
      ),
    );
    montar();
    const indice = await screen.findByRole("navigation", { name: "Índice de capítulos" });
    const [primero, segundo] = within(indice).getAllByRole("link");
    expect(primero).not.toHaveTextContent("cambió");
    expect(segundo).toHaveTextContent("cambió");
    expect(document.getElementById("capitulo-2")).toHaveAttribute("data-cambiado", "true");
  });

  it("RF-71: cada hecho sale en su grupo con un enlace por capítulo, y el que no se usa lo dice", async () => {
    montar();
    const personajes = await screen.findByRole("region", { name: "Personajes" });
    const ines = within(personajes).getByRole("navigation", { name: "Capítulos de Inés de Salcedo" });
    expect(within(ines).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "#capitulo-1",
      "#capitulo-2",
    ]);
    const lugares = screen.getByRole("region", { name: "Lugares" });
    expect(within(lugares).getByText("Triana")).toBeInTheDocument();
    expect(within(lugares).getByText("No aparece en ningún capítulo.")).toBeInTheDocument();
  });

  it("RF-71: la biblia que se pide es la de la versión que se lee", async () => {
    const pedidas: (string | null)[] = [];
    servidor.use(
      http.get(`${API}/obras/:id/manuscrito`, () => HttpResponse.json(manuscrito({ version: 3 }))),
      http.get(`${API}/obras/:id/hechos`, ({ request }) => {
        pedidas.push(new URL(request.url).searchParams.get("version"));
        return HttpResponse.json([]);
      }),
    );
    montar();
    expect(await screen.findByText("La biblia de esta versión todavía no tiene fichas.")).toBeInTheDocument();
    expect(pedidas).toEqual(["3"]);
  });
});

describe("leer una versión (SPEC2 RF-72) y descargarla (RF-77)", () => {
  it("elegir una versión la pone en la dirección y la pide; el PDF es el de la versión leída", async () => {
    const usuario = userEvent.setup();
    const pedidas: (string | null)[] = [];
    servidor.use(
      http.get(`${API}/obras/:id/versiones`, () =>
        HttpResponse.json([version({ publicada: true }), version({ numero: 2, base: 1, capitulos_cambiados: [2] })]),
      ),
      http.get(`${API}/obras/:id/manuscrito`, ({ request }) => {
        const pedida = new URL(request.url).searchParams.get("version");
        pedidas.push(pedida);
        return HttpResponse.json(manuscrito({ version: pedida ? Number(pedida) : 1, publicada: !pedida }));
      }),
    );
    montar();
    expect(await screen.findByText("Versión 1 · publicada", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Descargar PDF" })).toHaveAttribute(
      "href",
      `${API}/obras/${ID_OBRA}/pdf?version=1`,
    );

    await usuario.selectOptions(screen.getByLabelText(/Leer la versión/), "2");
    expect(await screen.findByText("Versión 2 · sin publicar", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByLabelText("dirección")).toHaveTextContent(`/obras/${ID_OBRA}/manuscrito?version=2`);
    expect(pedidas).toEqual([null, "2"]);
    expect(screen.getByRole("link", { name: "Descargar PDF" })).toHaveAttribute(
      "href",
      `${API}/obras/${ID_OBRA}/pdf?version=2`,
    );
  });
});

describe("la lectura no enseña críticas ni defectos", () => {
  it("ni botón de críticas ni aviso en un capítulo marcado, y no las pide", async () => {
    const pedidas: string[] = [];
    servidor.use(
      http.get(`${API}/obras/:id/criticas`, ({ request }) => {
        pedidas.push(new URL(request.url).search);
        return HttpResponse.json([]);
      }),
    );
    montar();
    const segundo = (await screen.findAllByRole("article"))[1]!;
    expect(within(segundo).queryByRole("button", { name: /críticas/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/defectos/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/críticas abiertas/i)).not.toBeInTheDocument();
    expect(pedidas).toEqual([]);
  });
});

describe("el cambio del lector (SPEC2 RF-76)", () => {
  it("manda el hecho y el nombre nuevo, y dice qué versión nace y qué se reescribe", async () => {
    const usuario = userEvent.setup();
    let cuerpo: unknown = null;
    servidor.use(
      http.post(`${API}/obras/:id/cambios`, async ({ request }) => {
        cuerpo = await request.json();
        return HttpResponse.json(
          { id_obra: ID_OBRA, version: 2, capitulos_cambiados: [1, 3], estado: "en produccion" },
          { status: 202 },
        );
      }),
    );
    montar();
    const nala = (await screen.findByText("Nala")).closest("li")!;
    await usuario.click(within(nala as HTMLElement).getByRole("button", { name: "Cambiar el nombre" }));
    await usuario.type(within(nala as HTMLElement).getByLabelText("Nombre nuevo"), "Luna");
    await usuario.click(within(nala as HTMLElement).getByRole("button", { name: "Pedir el cambio" }));
    expect(await within(nala as HTMLElement).findByRole("status")).toHaveTextContent(
      "Nace la versión 2: se reescribirán los capítulos 1, 3.",
    );
    expect(cuerpo).toEqual({ hecho: "per_2", valor: "Luna" });
    await usuario.click(within(nala as HTMLElement).getByRole("link", { name: "Ver el avance" }));
    expect(await screen.findByText("Pantalla del avance")).toBeInTheDocument();
  });

  it("un rechazo del servidor se pinta tal cual y no decide nada por su cuenta", async () => {
    const usuario = userEvent.setup();
    servidor.use(
      http.post(`${API}/obras/:id/cambios`, () =>
        HttpResponse.json(
          { detail: "ningun capitulo de la version 1 menciona lug_1: no hay nada que reescribir" },
          { status: 409 },
        ),
      ),
    );
    montar();
    const triana = (await screen.findByText("Triana")).closest("li") as HTMLElement;
    await usuario.click(within(triana).getByRole("button", { name: "Cambiar el nombre" }));
    await usuario.type(within(triana).getByLabelText("Nombre nuevo"), "Hispalis");
    await usuario.click(within(triana).getByRole("button", { name: "Pedir el cambio" }));
    expect(await within(triana).findByRole("alert")).toHaveTextContent(
      "ningun capitulo de la version 1 menciona lug_1: no hay nada que reescribir",
    );
  });
});
