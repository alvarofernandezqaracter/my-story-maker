// El encargo en curso, guardado en el navegador en cada cambio (SPEC2 RF-06,
// RD-02). Es lo único que la interfaz guarda por su cuenta: la respuesta de la
// pasada no se guarda, es del servidor (RD-01).
import { useRef, useState } from "react";
import { borrar, escribir, leer } from "../../compartido/almacen-local";
import type { TipoDeContradiccion } from "../../compartido/api/tipos";
import type { Aportacion, Encargo } from "./peticion";

export const CLAVE = "my-story-maker.encargo";

export type BorradorGuardado = Encargo & {
  version: 1;
  idEntrevista: string | null;
};

const TIPOS: TipoDeContradiccion[] = ["edad_contra_tono", "texto_contra_campo"];

function esAportacion(v: unknown): v is Aportacion {
  if (typeof v !== "object" || v === null) return false;
  const a = v as Record<string, unknown>;
  return (
    typeof a.id === "string" &&
    (a.clase === "mensaje" || a.clase === "pegado") &&
    typeof a.texto === "string"
  );
}

function esGuardado(v: unknown): v is BorradorGuardado {
  if (typeof v !== "object" || v === null) return false;
  const g = v as Record<string, unknown>;
  return (
    g.version === 1 &&
    (g.idEntrevista === null || typeof g.idEntrevista === "string") &&
    typeof g.valores === "object" &&
    g.valores !== null &&
    Object.values(g.valores).every((x) => typeof x === "string") &&
    Array.isArray(g.camposTocados) &&
    g.camposTocados.every((x) => typeof x === "string") &&
    Array.isArray(g.aportaciones) &&
    g.aportaciones.every(esAportacion) &&
    Array.isArray(g.asumidas) &&
    g.asumidas.every((x) => TIPOS.includes(x as TipoDeContradiccion))
  );
}

export const VACIO: BorradorGuardado = {
  version: 1,
  idEntrevista: null,
  valores: {},
  camposTocados: [],
  aportaciones: [],
  asumidas: [],
};

/** Cómo empezó la pantalla: nuevo, con lo recuperado o sin poder recuperarlo. */
export type Origen = "nuevo" | "recuperado" | "ilegible";

function cargar(): { guardado: BorradorGuardado; origen: Origen } {
  const lectura = leer(CLAVE, esGuardado);
  if (lectura.estado === "leido") return { guardado: lectura.valor, origen: "recuperado" };
  return { guardado: VACIO, origen: lectura.estado === "vacio" ? "nuevo" : "ilegible" };
}

export function useBorrador() {
  const [inicio] = useState(cargar);
  const [guardado, setGuardado] = useState<BorradorGuardado>(inicio.guardado);
  const [sePuedeGuardar, setSePuedeGuardar] = useState(true);
  // Lo último escrito, para que dos cambios seguidos en el mismo gesto se
  // encadenen sin perder ninguno. Solo se toca desde los manejadores.
  const ultimo = useRef(inicio.guardado);

  /** Aplica el cambio y lo guarda en el navegador en el mismo gesto. */
  function cambiar(cambio: (previo: BorradorGuardado) => BorradorGuardado) {
    const siguiente = cambio(ultimo.current);
    ultimo.current = siguiente;
    setGuardado(siguiente);
    setSePuedeGuardar(escribir(CLAVE, siguiente));
  }

  /** Borra lo guardado: al lanzarse la obra o al descartar el encargo. */
  function descartar() {
    borrar(CLAVE);
    ultimo.current = VACIO;
    setGuardado(VACIO);
  }

  return { guardado, origen: inicio.origen, sePuedeGuardar, cambiar, descartar };
}
