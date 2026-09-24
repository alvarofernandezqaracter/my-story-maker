// Consulta al servidor con su estado visible: cargando, listo o fallo. Sin
// caché compartida: cada pantalla pide lo suyo al entrar. Si no hay servidor,
// reintenta sola cada 5 s y lo dice.
import { useEffect, useState } from "react";
import type { Resultado } from "./api/cliente";
import type { Fallo } from "./api/fallos";

export const REINTENTO_SIN_SERVIDOR_MS = 5000;

export type Consulta<T> =
  | { estado: "cargando"; datos: T | null; fallo: null; reintentar: () => void }
  | { estado: "listo"; datos: T; fallo: null; reintentar: () => void }
  | { estado: "fallo"; datos: T | null; fallo: Fallo; reintentar: () => void };

type Respuesta<T> = { para: string; datos: T | null; fallo: Fallo | null };

/**
 * `clave` decide cuándo se vuelve a pedir: cada clave distinta es una consulta
 * nueva. Mientras la última respuesta no sea de la clave vigente, está cargando.
 */
export function useConsulta<T>(pedir: () => Promise<Resultado<T>>, clave: string): Consulta<T> {
  const [vuelta, setVuelta] = useState(0);
  const [respuesta, setRespuesta] = useState<Respuesta<T>>({ para: "", datos: null, fallo: null });
  const vigente = `${clave}#${vuelta}`;
  const reintentar = () => setVuelta((v) => v + 1);

  useEffect(() => {
    let activa = true;
    let temporizador: ReturnType<typeof setTimeout> | null = null;
    void pedir().then((resultado) => {
      if (!activa) return;
      if (resultado.ok) {
        setRespuesta({ para: vigente, datos: resultado.datos, fallo: null });
        return;
      }
      setRespuesta((previa) => ({ para: vigente, datos: previa.datos, fallo: resultado.fallo }));
      if (resultado.fallo.tipo === "sin_servidor") {
        temporizador = setTimeout(() => setVuelta((v) => v + 1), REINTENTO_SIN_SERVIDOR_MS);
      }
    });
    return () => {
      activa = false;
      if (temporizador !== null) clearTimeout(temporizador);
    };
    // `pedir` cambia de identidad en cada render; lo que decide repetir es la clave.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vigente]);

  if (respuesta.para !== vigente) {
    return { estado: "cargando", datos: respuesta.datos, fallo: null, reintentar };
  }
  if (respuesta.fallo !== null) {
    return { estado: "fallo", datos: respuesta.datos, fallo: respuesta.fallo, reintentar };
  }
  return { estado: "listo", datos: respuesta.datos as T, fallo: null, reintentar };
}
