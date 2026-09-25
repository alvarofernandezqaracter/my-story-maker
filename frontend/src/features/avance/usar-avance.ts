// La foto inicial y después el flujo (SPEC2 RF-21, D-04). Aquí no se calcula
// nada del avance: se guarda lo último que mandó el servidor.
import { useEffect, useState } from "react";
import { seguirElAvance, type EstadoDelFlujo } from "../../compartido/api/avance";
import {
  detenerObra,
  reanudarObra,
  verObra,
  verProgresoAhora,
} from "../../compartido/api/cliente";
import type { Fallo } from "../../compartido/api/fallos";
import type { FichaDeObra, Progreso } from "../../compartido/api/tipos";
import { REINTENTO_SIN_SERVIDOR_MS } from "../../compartido/usar-consulta";

export type Situacion = "en_marcha" | "detenida" | "terminada";
export type Orden = "deteniendo" | "reanudando" | null;

type Foto = { ficha: FichaDeObra; progreso: Progreso };

async function pedirFoto(idObra: string): Promise<{ ok: true; foto: Foto } | { ok: false; fallo: Fallo }> {
  const [ficha, progreso] = await Promise.all([verObra(idObra), verProgresoAhora(idObra)]);
  if (!ficha.ok) return { ok: false, fallo: ficha.fallo };
  if (!progreso.ok) return { ok: false, fallo: progreso.fallo };
  return { ok: true, foto: { ficha: ficha.datos, progreso: progreso.datos } };
}

export function useAvance(idObra: string) {
  const [foto, setFoto] = useState<Foto | null>(null);
  const [falloDeCarga, setFalloDeCarga] = useState<Fallo | null>(null);
  const [intentoDeCarga, setIntentoDeCarga] = useState(0);
  const [conexion, setConexion] = useState<{ estado: EstadoDelFlujo; intentos: number }>({
    estado: "conectando",
    intentos: 0,
  });
  const [ultimaNoticia, setUltimaNoticia] = useState<number | null>(null);
  // El flujo se cierra al llegar `terminada`; una orden posterior lo reabre.
  const [flujoCerrado, setFlujoCerrado] = useState(false);
  const [sesionDelFlujo, setSesionDelFlujo] = useState(0);
  const [orden, setOrden] = useState<Orden>(null);
  const [falloDeOrden, setFalloDeOrden] = useState<Fallo | null>(null);

  const cargada = foto !== null;

  // 1. La foto de una sola vez, antes de engancharse al flujo.
  useEffect(() => {
    let vigente = true;
    let temporizador: ReturnType<typeof setTimeout> | null = null;
    void pedirFoto(idObra).then((resultado) => {
      if (!vigente) return;
      if (resultado.ok) {
        setFoto(resultado.foto);
        setFalloDeCarga(null);
        return;
      }
      setFalloDeCarga(resultado.fallo);
      if (resultado.fallo.tipo === "sin_servidor") {
        temporizador = setTimeout(() => setIntentoDeCarga((n) => n + 1), REINTENTO_SIN_SERVIDOR_MS);
      }
    });
    return () => {
      vigente = false;
      if (temporizador !== null) clearTimeout(temporizador);
    };
  }, [idObra, intentoDeCarga]);

  // 2. Solo después, el flujo. Cada `progreso` reemplaza al anterior.
  useEffect(() => {
    if (!cargada || flujoCerrado) return;
    return seguirElAvance(idObra, {
      alProgreso: (progreso) => {
        setFoto((previa) => (previa ? { ...previa, progreso } : previa));
        setUltimaNoticia(Date.now());
      },
      alEstado: (estado, intentos) => setConexion({ estado, intentos }),
      alTerminar: () => {
        setFlujoCerrado(true);
        // 4. Detenida o terminada lo dice el campo `detenida` de la foto nueva.
        void pedirFoto(idObra).then((r) => {
          if (r.ok) setFoto(r.foto);
        });
      },
    });
  }, [idObra, cargada, flujoCerrado, sesionDelFlujo]);

  // 3. Los recuentos de capítulos solo vienen en la ficha: se piden otra vez
  // cuando cambia el capítulo en curso o la detención.
  const capitulo = foto?.progreso.capitulo_en_curso;
  const detenida = foto?.progreso.detenida;
  useEffect(() => {
    if (capitulo === undefined) return;
    let vigente = true;
    void verObra(idObra).then((r) => {
      if (vigente && r.ok) setFoto((previa) => (previa ? { ...previa, ficha: r.datos } : previa));
    });
    return () => {
      vigente = false;
    };
  }, [idObra, capitulo, detenida]);

  async function ordenar(tipo: "deteniendo" | "reanudando", motivo = "") {
    setOrden(tipo);
    setFalloDeOrden(null);
    const resultado = tipo === "deteniendo" ? await detenerObra(idObra, motivo) : await reanudarObra(idObra);
    if (!resultado.ok) {
      setOrden(null);
      setFalloDeOrden(resultado.fallo);
      return;
    }
    const nueva = await pedirFoto(idObra);
    if (nueva.ok) setFoto(nueva.foto);
    setOrden(null);
    if (flujoCerrado) {
      setFlujoCerrado(false);
      setSesionDelFlujo((n) => n + 1);
    }
  }

  let situacion: Situacion | null = null;
  if (foto) {
    // Una obra que el servidor ya da por terminada o publicada no está en marcha
    // aunque el flujo siga abierto (SPEC1 RF-205).
    const acabada = foto.ficha.situacion === "terminada" || foto.ficha.situacion === "publicada";
    if (foto.progreso.detenida) situacion = "detenida";
    else situacion = flujoCerrado || acabada ? "terminada" : "en_marcha";
  }

  return {
    foto,
    falloDeCarga,
    reintentarCarga: () => setIntentoDeCarga((n) => n + 1),
    conexion: flujoCerrado ? null : conexion,
    ultimaNoticia,
    situacion,
    orden,
    falloDeOrden,
    detener: (motivo: string) => void ordenar("deteniendo", motivo),
    reanudar: () => void ordenar("reanudando"),
  };
}
