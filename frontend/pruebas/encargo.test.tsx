import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes, useParams } from "react-router";
import { describe, expect, it } from "vitest";
import { MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";
import type { PeticionDeEntrevista } from "../src/compartido/api/tipos";
import { PantallaDelEncargo } from "../src/features/encargo/PantallaDelEncargo";
import { construirPeticion } from "../src/features/encargo/peticion";
import { CLAVE } from "../src/features/encargo/usar-borrador";
import { API, pasada, servidor, sinServidor } from "./servidor";

function AvanceFalso() {
  const { idObra } = useParams();
  return <p>Avance de {idObra}</p>;
}

function montar() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<PantallaDelEncargo />} />
        <Route path="/obras/:idObra" element={<AvanceFalso />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Registra cada pasada que llega al servidor simulado y contesta con `respuestas` en orden. */
function grabarPasadas(respuestas: ((n: number) => Response)[]) {
  const recibidas: { ruta: string; cuerpo: PeticionDeEntrevista }[] = [];
  const contestar = async (ruta: string, request: Request) => {
    recibidas.push({ ruta, cuerpo: (await request.json()) as PeticionDeEntrevista });
    const respuesta = respuestas[recibidas.length - 1] ?? respuestas[respuestas.length - 1];
    return respuesta!(recibidas.length);
  };
  servidor.use(
    http.post(`${API}/entrevistas`, ({ request }) => contestar("/entrevistas", request)),
    http.post(`${API}/entrevistas/:id/pasadas`, ({ request, params }) =>
      contestar(`/entrevistas/${String(params.id)}/pasadas`, request),
    ),
  );
  return recibidas;
}

const pendiente = (cambios = {}) => () =>
  HttpResponse.json(pasada({ estado: "pendiente", ...cambios }), { status: 201 });
const lanzada = () =>
  HttpResponse.json(pasada({ estado: "lanzada", id_obra: "obra-9", numero: 2 }), { status: 201 });

describe("el encargo (SPEC2 §4.1)", () => {
  it("RF-01: la primera pasada abre la entrevista y la segunda cuelga de su id", async () => {
    const usuario = userEvent.setup();
    const recibidas = grabarPasadas([pendiente({ numero: 1 }), pendiente({ numero: 2 })]);
    montar();
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "Una novela para mi abuela");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("El Entrevistador · pasada 1");
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "En Sevilla");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("El Entrevistador · pasada 2");
    expect(recibidas.map((r) => r.ruta)).toEqual(["/entrevistas", "/entrevistas/ent-1/pasadas"]);
  });

  it("RF-02: la tercera pasada lleva los dos mensajes, el texto pegado, la ficha y la contradicción asumida", async () => {
    const usuario = userEvent.setup();
    const choque = {
      contradicciones: [
        { tipo: "edad_contra_tono" as const, campos: ["destinatario.edad", "destinatario.tono"], evidencia: "tiene 8 años", asumida: false },
      ],
    };
    const recibidas = grabarPasadas([pendiente(choque), pendiente(choque), pendiente()]);
    montar();
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "Primero");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("El Entrevistador · pasada 1");

    await usuario.click(screen.getByRole("button", { name: "Pegar un texto" }));
    await usuario.type(screen.getByLabelText(/Pega aquí/), "Querida abuela:");
    await usuario.click(screen.getByRole("button", { name: "Añadir el texto" }));
    await usuario.type(screen.getByLabelText(/^Edad/), "8");
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "Segundo");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(recibidas).toHaveLength(2));
    await screen.findByRole("button", { name: "Darla por buena" });

    await usuario.click(screen.getByRole("button", { name: "Darla por buena" }));
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(recibidas).toHaveLength(3));

    expect(recibidas[2]!.cuerpo).toEqual({
      borrador: { destinatario: { edad: 8 } },
      textos: ["Primero", "Querida abuela:", "Segundo"],
      contradicciones_asumidas: ["edad_contra_tono"],
    });
  });

  it("RF-04: «Darla por buena» marca la tarjeta, que sigue a la vista, y se puede deshacer", async () => {
    const usuario = userEvent.setup();
    grabarPasadas([
      pendiente({
        contradicciones: [
          { tipo: "texto_contra_campo", campos: ["destinatario.edad"], evidencia: "cumple 90", asumida: false },
        ],
      }),
    ]);
    montar();
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    const tarjeta = (await screen.findByText("Un texto pegado dice otra cosa que un campo")).closest("article")!;
    await usuario.click(within(tarjeta).getByRole("button", { name: "Darla por buena" }));
    expect(within(tarjeta).getByText(/La das por buena/)).toBeInTheDocument();
    expect(within(tarjeta).getByText("cumple 90")).toBeInTheDocument();
    await usuario.click(within(tarjeta).getByRole("button", { name: "Deshacer" }));
    expect(within(tarjeta).getByRole("button", { name: "Darla por buena" })).toBeInTheDocument();
  });

  it("RF-05: una pasada lanzada salta sola al avance y deja el almacenamiento vacío", async () => {
    const usuario = userEvent.setup();
    grabarPasadas([lanzada]);
    montar();
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "Todo dicho");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Avance de obra-9")).toBeInTheDocument();
    expect(window.localStorage.getItem(CLAVE)).toBeNull();
  });

  it("RF-06 / OBJ-03: lo escrito y pegado sobrevive a desmontar y volver a montar", async () => {
    const usuario = userEvent.setup();
    const primera = montar();
    await usuario.type(screen.getByLabelText(/^Título/), "La luz de Triana");
    await usuario.click(screen.getByRole("button", { name: "Pegar un texto" }));
    await usuario.type(screen.getByLabelText(/Pega aquí/), "Una carta larga");
    await usuario.click(screen.getByRole("button", { name: "Añadir el texto" }));
    primera.unmount();

    montar();
    expect(screen.getByLabelText(/^Título/)).toHaveValue("La luz de Triana");
    expect(screen.getByText("Texto pegado · 1")).toBeInTheDocument();
    expect(screen.getByText(/Tu encargo está guardado/)).toBeInTheDocument();
  });

  it("RF-06: un almacenamiento que lanza no rompe la pantalla y avisa de que no se guarda", async () => {
    const usuario = userEvent.setup();
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("lleno");
    };
    try {
      montar();
      await usuario.type(screen.getByLabelText(/^Título/), "Algo");
      expect(await screen.findByText(/no deja guardar el encargo/)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Título/)).toHaveValue("Algo");
      expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled();
    } finally {
      Storage.prototype.setItem = original;
    }
  });

  it("RF-08: el 422 por tamaño se enseña literal y no desaparece ningún texto", async () => {
    const usuario = userEvent.setup();
    const mensaje = "La pasada ocupa 120000 tokens, el tope es 100000 y sobran 20000";
    grabarPasadas([() => HttpResponse.json({ detail: mensaje }, { status: 422 })]);
    montar();
    await usuario.click(screen.getByRole("button", { name: "Pegar un texto" }));
    await usuario.type(screen.getByLabelText(/Pega aquí/), "Texto enorme");
    await usuario.click(screen.getByRole("button", { name: "Añadir el texto" }));
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText(mensaje)).toBeInTheDocument();
    expect(screen.getByText("Texto pegado · 1")).toBeInTheDocument();
  });

  it("RF-61: un 422 de validación señala sus campos en la ficha", async () => {
    const usuario = userEvent.setup();
    grabarPasadas([
      () =>
        HttpResponse.json(
          { detalle: "borrador.capitulos_objetivo: debe ser menor que 200", campos: ["borrador.capitulos_objetivo"] },
          { status: 422 },
        ),
    ]);
    montar();
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("borrador.capitulos_objetivo: debe ser menor que 200")).toBeInTheDocument();
    const campo = document.querySelector('[data-ruta="capitulos_objetivo"]')!;
    expect(campo).toHaveClass("campo--senalado");
  });

  it("RF-62: sin servidor se dice distinto de un rechazo y «Reintentar» manda el mismo cuerpo", async () => {
    const usuario = userEvent.setup();
    const recibidas = grabarPasadas([() => sinServidor(), pendiente()]);
    montar();
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "Hola");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveAttribute("data-tipo", "sin_servidor");
    expect(aviso).toHaveTextContent(MENSAJE_SIN_SERVIDOR);
    await usuario.click(within(aviso).getByRole("button", { name: "Reintentar" }));
    await screen.findByText("El Entrevistador · pasada 1");
    expect(recibidas[1]!.cuerpo).toEqual(recibidas[0]!.cuerpo);
  });

  it("404: «Empezar de nuevo con lo que llevo» olvida la entrevista y conserva lo escrito", async () => {
    const usuario = userEvent.setup();
    const recibidas = grabarPasadas([
      pendiente(),
      () => HttpResponse.json({ detail: "No hay ninguna entrevista ent-1" }, { status: 404 }),
      pendiente(),
    ]);
    montar();
    await usuario.type(screen.getByLabelText("Escribe tu mensaje"), "Uno");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("El Entrevistador · pasada 1");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await usuario.click(await screen.findByRole("button", { name: "Empezar de nuevo con lo que llevo" }));
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(recibidas).toHaveLength(3));
    expect(recibidas[2]!.ruta).toBe("/entrevistas");
    expect(recibidas[2]!.cuerpo.textos).toEqual(["Uno"]);
  });
});

describe("criterios de aceptación de SPEC2 §10 con el servidor simulado", () => {
  it("1: sin edad ni tono, la carta pegada los completa y la obra se lanza sin salir de la web", async () => {
    const usuario = userEvent.setup();
    const recibidas = grabarPasadas([
      pendiente({ faltan: ["destinatario.edad", "destinatario.tono"] }),
      lanzada,
    ]);
    montar();
    await usuario.type(screen.getByLabelText(/^Nombre/), "Carmen");
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    const resultado = await screen.findByRole("region", { name: "Lo que ha entendido el sistema" });
    expect(within(resultado).getByText("Te falta decirme")).toBeInTheDocument();
    expect(document.querySelector('[data-ruta="destinatario.edad"]')).toHaveClass("campo--senalado");

    await usuario.click(screen.getByRole("button", { name: "Pegar un texto" }));
    await usuario.type(screen.getByLabelText(/Pega aquí/), "Cumple 82 y le gusta reír");
    await usuario.click(screen.getByRole("button", { name: "Añadir el texto" }));
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Avance de obra-9")).toBeInTheDocument();
    expect(recibidas[1]!.cuerpo.textos).toEqual(["Cumple 82 y le gusta reír"]);
  });

  it("3: una contradicción deja la obra sin lanzar hasta que se asume desde la pantalla", async () => {
    const usuario = userEvent.setup();
    const recibidas = grabarPasadas([
      pendiente({
        contradicciones: [
          { tipo: "edad_contra_tono", campos: ["destinatario.edad"], evidencia: "8 años y tono sombrío", asumida: false },
        ],
      }),
      lanzada,
    ]);
    montar();
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    await usuario.click(await screen.findByRole("button", { name: "Darla por buena" }));
    await usuario.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Avance de obra-9")).toBeInTheDocument();
    expect(recibidas[0]!.cuerpo.contradicciones_asumidas).toEqual([]);
    expect(recibidas[1]!.cuerpo.contradicciones_asumidas).toEqual(["edad_contra_tono"]);
  });
});

describe("peticion.ts: reglas de forma", () => {
  it("no manda cadenas vacías, manda números como número y listas solo si se tocaron", () => {
    expect(
      construirPeticion({
        valores: {
          titulo: "  ",
          capitulos_objetivo: "12",
          elenco_declarado: "Ana\n\nLuis\n",
          arcos: "",
          "destinatario.vetos": "",
        },
        camposTocados: ["elenco_declarado", "destinatario.vetos"],
        aportaciones: [
          { id: "a", clase: "mensaje", texto: "  " },
          { id: "b", clase: "pegado", texto: " Carta " },
        ],
        asumidas: [],
      }),
    ).toEqual({
      borrador: {
        capitulos_objetivo: 12,
        elenco_declarado: ["Ana", "Luis"],
        destinatario: { vetos: [] },
      },
      textos: [" Carta "],
      contradicciones_asumidas: [],
    });
  });
});
