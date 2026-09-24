import { afterEach, describe, expect, it, vi } from "vitest";
import { borrar, escribir, leer } from "../src/compartido/almacen-local";

const esNumero = (v: unknown): v is number => typeof v === "number";

describe("almacen-local", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lee lo que escribe", () => {
    expect(escribir("clave", 7)).toBe(true);
    expect(leer("clave", esNumero)).toEqual({ estado: "leido", valor: 7 });
    borrar("clave");
    expect(leer("clave", esNumero)).toEqual({ estado: "vacio" });
  });

  it("lo guardado que no pasa la validación es ilegible, no revienta", () => {
    window.localStorage.setItem("clave", "{no es json");
    expect(leer("clave", esNumero)).toEqual({ estado: "ilegible" });
    window.localStorage.setItem("clave", '"texto"');
    expect(leer("clave", esNumero)).toEqual({ estado: "ilegible" });
  });

  it("un almacenamiento que lanza excepción no rompe nada", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("lleno");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    expect(leer("clave", esNumero)).toEqual({ estado: "ilegible" });
    expect(escribir("clave", 1)).toBe(false);
    expect(() => borrar("clave")).not.toThrow();
  });
});
