import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { seguirElAvance } from "../src/compartido/api/avance";
import { MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";
import { PantallaDelAvance } from "../src/features/avance/PantallaDelAvance";
import { EventSourceFalso } from "./EventSourceFalso";
import { API, confirmacion, ficha, ID_OBRA, progreso, servidor, sinServidor } from "./servidor";

function montar(id = ID_OBRA) {
  return render(
    <MemoryRouter initialEntries={[`/obras/${id}`]}>
      <Routes>
        <Route path="/obras/:idObra" element={<PantallaDelAvance />} />
        <Route path="/obras/:idObra/manuscrito" element={<p>Lectura</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  EventSourceFalso.reiniciar();
  vi.stubGlobal("EventSource", EventSourceFalso);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("el avance (SPEC2 §4.2)", () => {
  it("RF-21: se pinta con la foto antes de que el flujo mande nada, y solo después se engancha", async () => {
    montar();
    expect(await screen.findByText("La luz de Triana")).toBeInTheDocument();
    expect(screen.getByTestId("tokens")).toHaveTextContent("12.340 de 100.000");
    expect(screen.getByText("redactar_escena")).toBeInTheDocument();
    await waitFor(() => expect(EventSourceFalso.creadas).toHaveLength(1));
    expect(EventSourceFalso.ultima().url).toBe(`${API}/obras/${ID_OBRA}/progreso`);
  });

  it("RF-20: cada `progreso` repinta capítulo, tareas y tokens", async () => {
    montar();
    await screen.findByText("La luz de Triana");
    await waitFor(() => expect(EventSourceFalso.creadas).toHaveLength(1));
    const flujo = EventSourceFalso.ultima();
    act(() => {
      flujo.abrir();
      flujo.progreso(
        progreso({
          capitulo_en_curso: 3,
          tokens_de_entrada_concurrentes: 45000,
          tareas_abiertas: [
            { rol: "verificador_de_continuidad", tarea: "verificar_capitulo", capitulo: 3, escena: null, tokens: 9000 },
          ],
        }),
      );
    });
    expect(screen.getByText("En directo")).toBeInTheDocument();
    expect(screen.getByTestId("capitulo-en-curso")).toHaveTextContent("3");
    expect(screen.getByTestId("tokens")).toHaveTextContent("45.000 de 100.000");
    expect(screen.getByText("verificar_capitulo")).toBeInTheDocument();
    expect(screen.queryByText("redactar_escena")).not.toBeInTheDocument();
  });

  it("RF-22: si el flujo se corta lo dice, se reabre solo y el último progreso sigue en pantalla", async () => {
    montar();
    await screen.findByText("La luz de Triana");
    await waitFor(() => expect(EventSourceFalso.creadas).toHaveLength(1));
    const primera = EventSourceFalso.ultima();
    act(() => {
      primera.abrir();
      primera.progreso(progreso({ tokens_de_entrada_concurrentes: 777 }));
    });
    vi.useFakeTimers();
    act(() => primera.cortar());
    expect(primera.cerrada).toBe(true);
    expect(screen.getByText(/Se ha cortado la conexión. Reconectando \(intento 1\)/)).toBeInTheDocument();
    expect(screen.getByTestId("tokens")).toHaveTextContent("777 de 100.000");

    act(() => vi.advanceTimersByTime(1000));
    expect(EventSourceFalso.creadas).toHaveLength(2);
    act(() => EventSourceFalso.ultima().abrir());
    expect(screen.getByText("En directo")).toBeInTheDocument();
  });

  it("RF-23: «Detener» manda el motivo; «Reanudar» aparece al estar detenida y vuelve a abrir el flujo", async () => {
    const usuario = userEvent.setup();
    let detenida = false;
    let motivoRecibido: unknown = null;
    servidor.use(
      http.get(`${API}/obras/:id/progreso/ahora`, () => HttpResponse.json(progreso({ detenida }))),
      http.post(`${API}/obras/:id/detener`, async ({ request }) => {
        motivoRecibido = await request.json();
        detenida = true;
        return HttpResponse.json(confirmacion(true, "revisar"));
      }),
      http.post(`${API}/obras/:id/reanudar`, () => {
        detenida = false;
        return HttpResponse.json(confirmacion(false));
      }),
    );
    montar();
    await screen.findByText("La luz de Triana");
    await waitFor(() => expect(EventSourceFalso.creadas).toHaveLength(1));

    await usuario.click(screen.getByRole("button", { name: "Detener" }));
    await usuario.type(screen.getByLabelText(/Por qué la detienes/), "revisar");
    await usuario.click(screen.getByRole("button", { name: "Detener la obra" }));
    expect(await screen.findByRole("button", { name: "Reanudar" })).toBeInTheDocument();
    expect(motivoRecibido).toEqual({ motivo: "revisar" });
    expect(screen.getByText("Detenida")).toBeInTheDocument();

    // El hilo acaba al detenerse: llega `terminada` y el flujo se cierra.
    act(() => EventSourceFalso.ultima().terminada());
    await waitFor(() => expect(EventSourceFalso.ultima().cerrada).toBe(true));
    const antes = EventSourceFalso.creadas.length;

    await usuario.click(screen.getByRole("button", { name: "Reanudar" }));
    await waitFor(() => expect(EventSourceFalso.creadas.length).toBe(antes + 1));
    expect(await screen.findByText("En marcha")).toBeInTheDocument();
  });

  it("RF-24: tras `terminada` con `detenida = false` dice «Terminada» y ofrece «Leer la novela»", async () => {
    montar();
    await screen.findByText("La luz de Triana");
    await waitFor(() => expect(EventSourceFalso.creadas).toHaveLength(1));
    servidor.use(
      http.get(`${API}/obras/:id/progreso/ahora`, () =>
        HttpResponse.json(progreso({ capitulo_en_curso: null, tareas_abiertas: [] })),
      ),
      http.get(`${API}/obras/:id`, () => HttpResponse.json(ficha({ capitulo_en_curso: null, capitulos_cerrados: 12 }))),
    );
    act(() => EventSourceFalso.ultima().terminada());
    expect(await screen.findByText("Terminada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Leer la novela" })).toBeInTheDocument();
    expect(screen.getByText("Ningún capítulo abierto ahora mismo")).toBeInTheDocument();
    expect(screen.getByText("Sin tareas abiertas ahora mismo.")).toBeInTheDocument();
  });

  it("404: el mensaje del servidor con enlace al encargo", async () => {
    servidor.use(
      http.get(`${API}/obras/:id`, () => HttpResponse.json({ detail: "No hay ninguna obra no-existe" }, { status: 404 })),
      http.get(`${API}/obras/:id/progreso/ahora`, () =>
        HttpResponse.json({ detail: "No hay ninguna obra no-existe" }, { status: 404 }),
      ),
    );
    montar("no-existe");
    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("No hay ninguna obra no-existe");
    expect(within(aviso).getByRole("link", { name: "Ir al encargo" })).toBeInTheDocument();
    expect(EventSourceFalso.creadas).toHaveLength(0);
  });
});

describe("avance.ts: el reenganche (RNF-04)", () => {
  it("espera 1, 2, 4, 8 y luego 15 s entre intentos, y deja de intentar al apagarse", () => {
    vi.useFakeTimers();
    const estados: string[] = [];
    const apagar = seguirElAvance(
      "o",
      { alProgreso: () => {}, alTerminar: () => {}, alEstado: (e, n) => estados.push(`${e}:${n}`) },
      (url) => new EventSourceFalso(url) as unknown as EventSource,
    );
    for (const segundos of [1, 2, 4, 8, 15, 15]) {
      const antes = EventSourceFalso.creadas.length;
      EventSourceFalso.ultima().cortar();
      vi.advanceTimersByTime(segundos * 1000 - 1);
      expect(EventSourceFalso.creadas.length).toBe(antes);
      vi.advanceTimersByTime(1);
      expect(EventSourceFalso.creadas.length).toBe(antes + 1);
    }
    expect(estados[0]).toBe("conectando:0");
    expect(estados).toContain("reconectando:6");
    apagar();
    EventSourceFalso.ultima().cortar();
    vi.advanceTimersByTime(60_000);
    expect(EventSourceFalso.ultima().cerrada).toBe(true);
  });
});

describe("criterio 5 de SPEC2 §10: servidor caído", () => {
  it("la pantalla del avance dice que no hay servidor y lo reintenta sola", async () => {
    servidor.use(
      http.get(`${API}/obras/:id`, sinServidor),
      http.get(`${API}/obras/:id/progreso/ahora`, sinServidor),
    );
    montar();
    expect(await screen.findByText(MENSAJE_SIN_SERVIDOR)).toBeInTheDocument();
    expect(screen.getByText(/Lo vuelvo a intentar solo/)).toBeInTheDocument();
  });
});
