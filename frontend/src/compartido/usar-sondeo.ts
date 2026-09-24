// Una consulta que se repite cada `periodoMs` mientras la pestaña está visible y
// se para mientras está oculta (SPEC2 RF-83). Mientras llega la vuelta nueva se
// sigue viendo la anterior: refrescar no vacía la pantalla.
import { useEffect, useState } from "react";
import type { Resultado } from "./api/cliente";
import { useConsulta, type Consulta } from "./usar-consulta";

export function useSondeo<T>(pedir: () => Promise<Resultado<T>>, clave: string, periodoMs: number): Consulta<T> {
  const [vuelta, setVuelta] = useState(0);
  useEffect(() => {
    let reloj: ReturnType<typeof setInterval> | null = null;
    const programar = () => {
      if (reloj !== null) clearInterval(reloj);
      reloj = null;
      if (document.visibilityState === "visible") reloj = setInterval(() => setVuelta((v) => v + 1), periodoMs);
    };
    const alVolver = () => {
      if (document.visibilityState === "visible") setVuelta((v) => v + 1);
      programar();
    };
    programar();
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      if (reloj !== null) clearInterval(reloj);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [periodoMs]);
  return useConsulta(pedir, `${clave}@${vuelta}`);
}
