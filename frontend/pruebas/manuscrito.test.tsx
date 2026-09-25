import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";
import { agrupar } from "../src/features/manuscrito/agrupar";
import { PantallaDelManuscrito } from "../src/features/manuscrito/PantallaDelManuscrito";
import { API, ID_OBRA, manuscrito, servidor, sinServidor } from "./servidor";

function montar(id = ID_OBRA) {
  return render(
    <MemoryRouter initialEntries={[`/obras/${id}/manuscrito`]}>
      <Routes>
        <Route path="/obras/:idObra/manuscrito" element={<PantallaDelManuscrito />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("la lectura (SPEC2 §4.3)", () => {
  it("RF-40: las unidades de dos capítulos se agrupan en orden, con sus escenas y párrafos", async () => {
    montar();
    const capitulos = await screen.findAllByRole("article");
    expect(capitulos.map((c) => c.id)).toEqual(["capitulo-1", "capitulo-2"]);
    const escenas = within(capitulos[0]!).getAllByRole("region");
    expect(escenas).toHaveLength(2);
    expect(within(escenas[0]!).getAllByText(/./, { selector: "p" }).map((p) => p.textContent)).toEqual([
      "Amanecía sobre el río.",
      "La barca esperaba.",
    ]);
    const indice = screen.getByRole("navigation", { name: "Índice de capítulos" });
    expect(within(indice).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "#capitulo-1",
      "#capitulo-2",
    ]);
  });

  it("un capítulo marcado se lee igual que los demás: sin aviso de defectos", async () => {
    montar();
    const [primero, segundo] = await screen.findAllByRole("article");
    expect(within(segundo!).queryByRole("note")).not.toBeInTheDocument();
    expect(within(primero!).queryByRole("note")).not.toBeInTheDocument();
  });

  it("la portada trae el título y las cifras de lectura, no las de calidad", async () => {
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "La luz de Triana" })).toBeInTheDocument();
    const cifras = screen.getByRole("list", { name: "La obra en cifras" });
    expect(cifras).toHaveTextContent("2 capítulos");
    expect(screen.queryByText(/marcados/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/críticas/i)).not.toBeInTheDocument();
  });

  it("sin texto aceptado lo dice y enlaza al avance; «Buscar texto nuevo» vuelve a pedirlo", async () => {
    const usuario = userEvent.setup();
    let unidades = manuscrito({ unidades: [] });
    servidor.use(http.get(`${API}/obras/:id/manuscrito`, () => HttpResponse.json(unidades)));
    montar();
    expect(await screen.findByText(/Aún no hay ningún capítulo aceptado/)).toBeInTheDocument();
    unidades = manuscrito();
    await usuario.click(screen.getByRole("button", { name: "Buscar texto nuevo" }));
    expect(await screen.findByText("Amanecía sobre el río.")).toBeInTheDocument();
  });

  it("el texto se pinta como texto, nunca como HTML", async () => {
    servidor.use(
      http.get(`${API}/obras/:id/manuscrito`, () =>
        HttpResponse.json(
          manuscrito({ unidades: [{ capitulo: 1, escena: "e1", texto: "<b>negrita</b>", capitulo_marcado: false }] }),
        ),
      ),
    );
    montar();
    expect(await screen.findByText("<b>negrita</b>")).toBeInTheDocument();
    expect(document.querySelector(".escena b")).toBeNull();
  });

  it("404: el mensaje del servidor", async () => {
    servidor.use(
      http.get(`${API}/obras/:id`, () => HttpResponse.json({ detail: "No hay ninguna obra x" }, { status: 404 })),
      http.get(`${API}/obras/:id/manuscrito`, () =>
        HttpResponse.json({ detail: "No hay ninguna obra x" }, { status: 404 }),
      ),
    );
    montar("x");
    expect(await screen.findByRole("alert")).toHaveTextContent("No hay ninguna obra x");
  });

  it("criterio 5: con el servidor caído dice qué pasa en vez de quedarse en blanco", async () => {
    servidor.use(http.get(`${API}/obras/:id`, sinServidor), http.get(`${API}/obras/:id/manuscrito`, sinServidor));
    montar();
    expect(await screen.findByText(MENSAJE_SIN_SERVIDOR)).toBeInTheDocument();
  });
});

describe("agrupar.ts", () => {
  it("respeta el orden de llegada y marca el capítulo si alguna unidad trae la marca", () => {
    const capitulos = agrupar([
      { capitulo: 2, escena: "a", texto: "x", capitulo_marcado: false },
      { capitulo: 2, escena: "b", texto: "y", capitulo_marcado: true },
      { capitulo: 1, escena: "a", texto: "z", capitulo_marcado: false },
    ]);
    expect(capitulos.map((c) => [c.capitulo, c.marcado, c.escenas.length])).toEqual([
      [2, true, 2],
      [1, false, 1],
    ]);
  });
});
