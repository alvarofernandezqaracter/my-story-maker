import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";
import { PantallaDelTaller, PERIODO_DEL_TALLER_MS } from "../src/features/taller/PantallaDelTaller";
import { PantallaDeTareas } from "../src/features/tareas/PantallaDeTareas";
import { API, ID_OBRA, ficha, obraDelTaller, servidor, sinServidor } from "./servidor";

function montar(ruta = "/") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/" element={<PantallaDelTaller />} />
        <Route path="/encargo" element={<h1>El encargo</h1>} />
        <Route path="/obras/:idObra" element={<h1>El avance</h1>} />
        <Route path="/obras/:idObra/tareas" element={<PantallaDeTareas />} />
      </Routes>
    </MemoryRouter>,
  );
}

const cuatro = () => [
  obraDelTaller({ id_obra: "o1", titulo: "La luz de Triana", situacion: "en_produccion", capitulos_cerrados: 2 }),
  obraDelTaller({
    id_obra: "o2",
    titulo: "El códice de Toledo",
    epoca: "Toledo, 1492",
    situacion: "detenida",
    detenida: true,
    motivo_de_la_detencion: "redactar_escena agotó sus intentos",
    destinatario: null,
  }),
  obraDelTaller({ id_obra: "o3", titulo: "Salamanca", epoca: "Salamanca, 1570", situacion: "terminada" }),
  obraDelTaller({ id_obra: "o4", titulo: "Valladolid", epoca: "Valladolid, 1601", situacion: "publicada", version_publicada: 1 }),
  obraDelTaller({ id_obra: "o5", titulo: "Cádiz", epoca: "Cádiz, 1596", situacion: "en_produccion" }),
];

const columna = (nombre: RegExp) => screen.getByRole("listitem", { name: nombre });

describe("el taller (SPEC2 §4.11)", () => {
  it("RF-80, RF-82: una columna por situación, en su orden, cada una con su cuenta", async () => {
    servidor.use(http.get(`${API}/obras`, () => HttpResponse.json(cuatro())));
    montar();
    await screen.findByText("El códice de Toledo");

    const columnas = within(screen.getByRole("list", { name: "Obras por situación" })).getAllByRole("listitem");
    expect(columnas.map((c) => c.getAttribute("aria-label"))).toEqual([
      "En producción: 2",
      "Detenida: 1",
      "Terminada: 1",
      "Publicada: 1",
    ]);
    expect(within(columna(/^En producción/)).getByText("La luz de Triana")).toBeInTheDocument();
    expect(within(columna(/^En producción/)).getByText("Cádiz")).toBeInTheDocument();
    expect(within(columna(/^Detenida/)).getByText("El códice de Toledo")).toBeInTheDocument();
    expect(within(columna(/^Publicada/)).getByText("Valladolid")).toBeInTheDocument();
  });

  it("RF-80: la columna la dice el servidor, aunque los demás campos digan otra cosa", async () => {
    // `detenida` a falso y sin versión publicada, pero el servidor dice publicada:
    // la interfaz no combina campos para deducir la columna.
    servidor.use(
      http.get(`${API}/obras`, () =>
        HttpResponse.json([obraDelTaller({ id_obra: "x", titulo: "La que manda", situacion: "publicada" })]),
      ),
    );
    montar();
    await screen.findByText("La que manda");
    expect(within(columna(/^Publicada/)).getByText("La que manda")).toBeInTheDocument();
    expect(within(columna(/^En producción/)).getByText("Ninguna")).toBeInTheDocument();
  });

  it("RF-81: la tarjeta enseña lo que sirve el listado y lleva a su avance", async () => {
    servidor.use(http.get(`${API}/obras`, () => HttpResponse.json(cuatro())));
    montar();
    const tarjeta = await screen.findByRole("link", { name: "La luz de Triana, En producción" });
    expect(tarjeta).toHaveTextContent("Sevilla, 1587");
    expect(tarjeta).toHaveTextContent("Para Lucía");
    expect(tarjeta).toHaveTextContent("2 / 6");
    expect(within(tarjeta).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");

    const detenida = screen.getByRole("link", { name: "El códice de Toledo, Detenida" });
    expect(detenida).toHaveTextContent("redactar_escena agotó sus intentos");
    expect(detenida).not.toHaveTextContent("Para ");

    await userEvent.click(tarjeta);
    expect(await screen.findByRole("heading", { name: "El avance" })).toBeInTheDocument();
  });

  it("RF-82: sin obras lo dice y ofrece encargar la primera", async () => {
    servidor.use(http.get(`${API}/obras`, () => HttpResponse.json([])));
    montar();
    expect(await screen.findByRole("heading", { name: "Todavía no hay ninguna obra" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Encarga la primera" }));
    expect(await screen.findByRole("heading", { name: "El encargo" })).toBeInTheDocument();
  });

  it("RF-82: el filtro reparte solo lo que casa, sin volver a pedir", async () => {
    let pedidas = 0;
    servidor.use(
      http.get(`${API}/obras`, () => {
        pedidas += 1;
        return HttpResponse.json(cuatro());
      }),
    );
    montar();
    await screen.findByText("El códice de Toledo");
    const antes = pedidas;
    await userEvent.type(screen.getByRole("searchbox", { name: "Filtrar obras" }), "toledo");

    expect(screen.getByText("El códice de Toledo")).toBeInTheDocument();
    expect(screen.queryByText("La luz de Triana")).not.toBeInTheDocument();
    expect(columna(/^En producción/)).toHaveAttribute("aria-label", "En producción: 0");
    expect(pedidas).toBe(antes);
  });

  it("RF-83: sin servidor lo dice en vez de quedarse en blanco", async () => {
    servidor.use(http.get(`${API}/obras`, sinServidor));
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent(MENSAJE_SIN_SERVIDOR);
  });
});

describe("el refresco del taller (SPEC2 RF-83)", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  });

  it("vuelve a pedir solo, cambia la obra de columna y para con la pestaña oculta", async () => {
    let situacion: "en_produccion" | "detenida" = "en_produccion";
    let pedidas = 0;
    servidor.use(
      http.get(`${API}/obras`, () => {
        pedidas += 1;
        return HttpResponse.json([obraDelTaller({ id_obra: "o1", titulo: "La que cambia", situacion })]);
      }),
    );
    montar();
    await screen.findByText("La que cambia");
    expect(within(columna(/^En producción/)).getByText("La que cambia")).toBeInTheDocument();

    situacion = "detenida";
    await act(async () => {
      vi.advanceTimersByTime(PERIODO_DEL_TALLER_MS + 10);
    });
    expect(await within(columna(/^Detenida/)).findByText("La que cambia")).toBeInTheDocument();

    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    const oculta = pedidas;
    await act(async () => {
      vi.advanceTimersByTime(PERIODO_DEL_TALLER_MS * 3);
    });
    expect(pedidas).toBe(oculta);
  });
});

describe("la barra y el lateral (SPEC2 RF-84, RF-30)", () => {
  it("la barra marca el taller y lleva al encargo de una obra nueva", async () => {
    montar();
    const principal = screen.getByRole("navigation", { name: "Principal" });
    expect(within(principal).getByRole("link", { name: "Taller" })).toHaveClass("activa");
    await userEvent.click(screen.getByRole("link", { name: "+ Nueva obra" }));
    expect(await screen.findByRole("heading", { name: "El encargo" })).toBeInTheDocument();
  });

  it("el lateral de una obra enseña su título y la situación que dice el servidor", async () => {
    servidor.use(
      http.get(`${API}/obras/:id`, () => HttpResponse.json(ficha({ situacion: "terminada" }))),
    );
    montar(`/obras/${ID_OBRA}/tareas`);
    const lateral = screen.getByRole("complementary");
    expect(await within(lateral).findByText("Terminada")).toBeInTheDocument();
    expect(within(lateral).getByText("La luz de Triana")).toBeInTheDocument();
    expect(within(lateral).getByRole("link", { name: "Tareas" })).toHaveClass("activa");
  });
});
