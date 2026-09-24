import { useEffect, useState } from "react";

// Dice qué se está esperando y cuánto lleva. Nada gira en blanco (SPEC2 RF-60).
export function Espera({ que }: { que: string }) {
  const [segundos, setSegundos] = useState(0);
  useEffect(() => {
    const reloj = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(reloj);
  }, []);
  return (
    <p className="espera" role="status" aria-live="polite">
      <span className="espera__punto" aria-hidden="true" />
      {que} · {segundos} s
    </p>
  );
}
