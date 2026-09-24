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
    expect(within(segunda).getByRole("button", { name: "Publicar" })).toBeInTheDocument();

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

describe("publicar y la puerta (SPEC2 RF-74)", () => {
  it("la puerta pinta cada fallo tal como viene, también el de un validador que la interfaz no conoce", async () => {
    const usuario = userEvent.setup();
    servidor.use(
      http.get(`${API}/obras/:id/versiones`, () => HttpResponse.json(TRES)),
      http.get(`${API}/obras/:id/versiones/:n/puerta`, () =>
        HttpResponse.json(
          puerta({
            version: 2,
            pasa: false,
            fallos: [
              { validador: "longitud", capitulo: 2, detalle: "el capitulo tiene 200 palabras" },
              // Un validador que llega de otra tarea: sale sin tocar la interfaz.
              { validador: "demostrador_formal", capitulo: null, detalle: "Ines esta en dos sitios" } as never,
            ],
          }),
        ),
      ),
    );
    montar();
    const segunda = await screen.findByRole("listitem", { name: "Versión 2" });
    await usuario.click(within(segunda).getByRole("button", { name: "Comprobar la puerta" }));
    const lista = await within(segunda).findByRole("list", { name: "Por qué no pasa la versión 2" });
    const fallos = within(lista).getAllByRole("listitem").map((li) => li.textContent);
    expect(fallos).toEqual([
      "longitud · capítulo 2 · el capitulo tiene 200 palabras",
      "demostrador_formal · de la obra · Ines esta en dos sitios",
    ]);
  });

  it("publicar una que no pasa enseña el rechazo y los fallos del 409", async () => {
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
    await usuario.click(within(segunda).getByRole("button", { name: "Publicar" }));
    expect(await within(segunda).findByRole("alert")).toHaveTextContent(
      "la version 2 no pasa la puerta de publicacion: 1 fallo(s)",
    );
    expect(within(segunda).getByRole("list", { name: "Por qué no pasa la versión 2" })).toHaveTextContent(
      "nombres · capítulo 3 · «Inés» donde la biblia escribe «Ines»",
    );
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
        return HttpResponse.json({ id_obra: ID_OBRA, version: 2, publicada_en: "2026-09-24T13:00:00Z" });
      }),
    );
    montar();
    const segunda = await screen.findByRole("listitem", { name: "Versión 2" });
    await usuario.click(within(segunda).getByRole("button", { name: "Publicar" }));
    expect(await within(segunda).findByText("Publicada")).toBeInTheDocument();
    expect(within(screen.getByRole("listitem", { name: "Versión 1" })).queryByText("Publicada")).not.toBeInTheDocument();
  });
});
