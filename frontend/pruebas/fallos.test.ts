import { describe, expect, it } from "vitest";
import { falloDesde, MENSAJE_SIN_SERVIDOR } from "../src/compartido/api/fallos";

describe("fallos: los cuatro formatos de error (SPEC2 RF-61, RF-62)", () => {
  it("un {detail: texto} es un rechazo con ese texto, sin tocarlo", () => {
    expect(falloDesde(404, { detail: "No hay ninguna obra obra-x" })).toEqual({
      tipo: "rechazo",
      estado: 404,
      mensaje: "No hay ninguna obra obra-x",
      campos: [],
    });
  });

  it("un {detalle, campos} es un rechazo con sus rutas", () => {
    expect(
      falloDesde(422, {
        detalle: "Falta un campo obligatorio del brief: destinatario.edad",
        campos: ["destinatario.edad"],
      }),
    ).toEqual({
      tipo: "rechazo",
      estado: 422,
      mensaje: "Falta un campo obligatorio del brief: destinatario.edad",
      campos: ["destinatario.edad"],
    });
  });

  it("un {detail: [errores]} junta los mensajes y quita el primer tramo de cada ruta", () => {
    const fallo = falloDesde(422, {
      detail: [
        { loc: ["body", "borrador", "capitulos_objetivo"], msg: "debe ser mayor que 0", type: "x" },
        { loc: ["body", "textos", 0], msg: "vacío", type: "y" },
      ],
    });
    expect(fallo).toEqual({
      tipo: "rechazo",
      estado: 422,
      mensaje: "debe ser mayor que 0; vacío",
      campos: ["borrador.capitulos_objetivo", "textos.0"],
    });
  });

  it("cualquier otra cosa, como un 500 sin JSON del proxy, es que no hay servidor", () => {
    expect(falloDesde(500, "")).toEqual({ tipo: "sin_servidor", mensaje: MENSAJE_SIN_SERVIDOR });
    expect(falloDesde(502, undefined)).toEqual({ tipo: "sin_servidor", mensaje: MENSAJE_SIN_SERVIDOR });
  });
});
