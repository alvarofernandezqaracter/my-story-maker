import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";
import { PantallaDeVersiones } from "../src/features/versiones/PantallaDeVersiones";
import { API, ID_OBRA, puerta, servidor, sinServidor, version } from "./servidor";

function montar() {
  return render(
    <MemoryRouter initialEntries={[`/obras/${ID_OBRA}/versiones`]}>
      <Routes>
        <Route path="/obras/:idObra/versiones" element={<PantallaDeVersiones />} />
      </Routes>
    </MemoryRouter>,
  );
}

const TRES = [
  version({ publicada: true }),
  version({ numero: 2, base: 1, capitulos_cambiados: [2, 3] }),
  version({
    numero: 3,
    base: 2,
    capitulos_cambiados: [1, 3],
    terminada: false,
    terminada_en: null,
    cambio: { hecho: "per_2", tipo: "Personaje", anterior: "Toby", nuevo: "Nala" },
  }),
];

describe("la pantalla de versiones (SPEC2 RF-73)", () => {
  it("cada versión dice de dónde sale, qué reescribe, si terminó y cuál es la publicada", async () => {
    servidor.use(http.get(`${API}/obras/:id/versiones`, () => HttpResponse.json(TRES)));
    montar();
    const tercera = await screen.findByRole("listitem", { name: "Versión 3" });
    expect(tercera).toHaveTextContent("por un cambio del lector: «Toby» pasa a llamarse «Nala»");
    expect(tercera).toHaveTextContent("Capítulos que reescribe: 1, 3.");
    expect(tercera).toHaveTextContent("En producción");
    expect(within(tercera).queryByRole("button", { name: "Publicar" })).not.toBeInTheDocument();

    const segunda = screen.getByRole("listitem", { name: "Versión 2" });
    expect(segunda).toHaveTextContent("rehecha desde el capítulo 2");
    expect(await within(segunda).findByRole("button", { name: "Publicar" })).toBeInTheDocument();

    const primera = screen.getByRole("listitem", { name: "Versión 1" });
    expect(primera).toHaveTextContent("Nace con el alta de la obra.");
    expect(primera).toHaveTextContent("Publicada");
    expect(within(primera).queryByRole("button", { name: "Publicar" })).not.toBeInTheDocument();
  });

  it("con el servidor caído dice qué pasa", async () => {
    servidor.use(http.get(`${API}/obras/:id/versiones`, sinServidor));
    montar();
    expect(await screen.findByText(MENSAJE_SIN_SERVIDOR)).toBeInTheDocument();
  });
});

describe("publicar (SPEC2 RF-74)", () => {
  it("una versión terminada que no pasa la puerta no ofrece publicar ni enseña sus fallos", async () => {
    servidor.use(
      http.get(`${API}/obras/:id/versiones`, () => HttpResponse.json(TRES)),
      http.get(`${API}/obras/:id/versiones/:n/puerta`, () =>
        HttpResponse.json(
          puerta({
            version: 2,
            pasa: false,
            fallos: [{ validador: "longitud", capitulo: 2, detalle: "el capitulo tiene 200 palabras" }],
          }),
        ),
      ),
    );
    montar();
    const segunda = await screen.findByRole("listitem", { name: "Versión 2" });
    expect(await within(segunda).findByText("Pendiente de publicar")).toBeInTheDocument();
    expect(within(segunda).queryByRole("button", { name: "Publicar" })).not.toBeInTheDocument();
    expect(screen.queryByText(/200 palabras/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /puerta/i })).not.toBeInTheDocument();
  });

  it("si el servidor rechaza publicar por la puerta, no enseña los fallos", async () => {
    const usuario = userEvent.setup();
    servidor.use(
      http.get(`${API}/obras/:id/versiones`, () => HttpResponse.json(TRES)),
      http.post(`${API}/obras/:id/versiones/:n/publicar`, () =>
        HttpResponse.json(
          {
            detail: "la version 2 no pasa la puerta de publicacion: 1 fallo(s)",
            puerta: puerta({
              version: 2,
              pasa: false,
              fallos: [{ validador: "nombres", capitulo: 3, detalle: "«Inés» donde la biblia escribe «Ines»" }],
            }),
          },
          { status: 409 },
        ),
      ),
    );
    montar();
    const segunda = await screen.findByRole("listitem", { name: "Versión 2" });
    await usuario.click(await within(segunda).findByRole("button", { name: "Publicar" }));
    expect(await within(segunda).findByText("Pendiente de publicar")).toBeInTheDocument();
    expect(screen.queryByText(/no pasa la puerta/)).not.toBeInTheDocument();
    expect(screen.queryByText(/biblia escribe/)).not.toBeInTheDocument();
  });

  it("publicar una que pasa lo dice y vuelve a pedir la lista", async () => {
    const usuario = userEvent.setup();
    let publicada = false;
    servidor.use(
      http.get(`${API}/obras/:id/versiones`, () =>
        HttpResponse.json([
          version({ publicada: !publicada }),
          version({ numero: 2, base: 1, capitulos_cambiados: [2, 3], publicada }),
        ]),
      ),
      http.post(`${API}/obras/:id/versiones/:n/publicar`, () => {
        publicada = true;
        return HttpResponse.json({
          id_obra: ID_OBRA,
          version: 2,
          publicada_en: "2026-09-24T13:00:00Z",
          comprobacion_formal: "sin_comprobacion",
        });
      }),
    );
    montar();
    const segunda = await screen.findByRole("listitem", { name: "Versión 2" });
    await usuario.click(await within(segunda).findByRole("button", { name: "Publicar" }));
    expect(await within(segunda).findByText("Publicada")).toBeInTheDocument();
    expect(within(screen.getByRole("listitem", { name: "Versión 1" })).queryByText("Publicada")).not.toBeInTheDocument();
    // Sin Lean en el servidor se publica igual, y se dice (SPEC1 RF-155).
    expect(within(segunda).getByText(/Sin comprobación formal/)).toBeInTheDocument();
  });
});
