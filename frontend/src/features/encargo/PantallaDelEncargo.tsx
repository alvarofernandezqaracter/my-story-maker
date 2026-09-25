import { useState } from "react";
import { useNavigate } from "react-router";
import { abrirEntrevista, pasarEntrevista } from "../../compartido/api/cliente";
import type { Fallo } from "../../compartido/api/fallos";
import type {
  PasadaDeEntrevista,
  PeticionDeEntrevista,
  TipoDeContradiccion,
} from "../../compartido/api/tipos";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { Espera } from "../../compartido/componentes/Espera";
import { campoDe } from "./campos";
import { Conversacion } from "./Conversacion";
import { FichaDelEncargo } from "./FichaDelEncargo";
import { construirPeticion, type Aportacion } from "./peticion";
import { Resultado } from "./Resultado";
import { useBorrador, type BorradorGuardado } from "./usar-borrador";
import "./encargo.css";

type EnvioFallido = { fallo: Fallo; cuerpo: PeticionDeEntrevista };
type Confirmando = "descartar" | "empezar_nuevo" | null;

let contador = 0;
const nuevoId = () => `${Date.now().toString(36)}-${(contador += 1)}`;

/** La ruta de un campo rechazado, tal como la nombra la ficha. */
const rutaEnLaFicha = (campo: string) => campo.replace(/^borrador\./, "");

// La conversación que completa el encargo (SPEC2 §4.1). Cada envío es una
// pasada sin estado: se manda todo lo acumulado en el navegador.
export function PantallaDelEncargo() {
  const navegar = useNavigate();
  const { guardado, origen, sePuedeGuardar, cambiar, descartar } = useBorrador();
  const [pasada, setPasada] = useState<PasadaDeEntrevista | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [fallido, setFallido] = useState<EnvioFallido | null>(null);
  const [confirmando, setConfirmando] = useState<Confirmando>(null);

  async function mandar(cuerpo: PeticionDeEntrevista, idEntrevista: string | null) {
    setEnviando(true);
    setFallido(null);
    const resultado = idEntrevista
      ? await pasarEntrevista(idEntrevista, cuerpo)
      : await abrirEntrevista(cuerpo);
    setEnviando(false);
    if (!resultado.ok) {
      setFallido({ fallo: resultado.fallo, cuerpo });
      return;
    }
    const respuesta = resultado.datos;
    if (respuesta.estado === "lanzada" && respuesta.id_obra) {
      // La obra se lanza sola, sin confirmación (SPEC2 RF-05). Lo guardado se
      // descarta y volver atrás no reabre la entrevista.
      descartar();
      void navegar(`/obras/${encodeURIComponent(respuesta.id_obra)}`, { replace: true });
      return;
    }
    cambiar((g) => ({ ...g, idEntrevista: respuesta.id_entrevista }));
    setPasada(respuesta);
  }

  function enviar(mensajeNuevo: string) {
    let siguiente: BorradorGuardado = guardado;
    if (mensajeNuevo.trim() !== "") {
      const aportacion: Aportacion = { id: nuevoId(), clase: "mensaje", texto: mensajeNuevo };
      siguiente = { ...guardado, aportaciones: [...guardado.aportaciones, aportacion] };
      cambiar(() => siguiente);
    }
    void mandar(construirPeticion(siguiente), siguiente.idEntrevista);
  }

  function pegar(texto: string) {
    const aportacion: Aportacion = { id: nuevoId(), clase: "pegado", texto };
    cambiar((g) => ({ ...g, aportaciones: [...g.aportaciones, aportacion] }));
  }

  function quitar(id: string) {
    cambiar((g) => ({ ...g, aportaciones: g.aportaciones.filter((a) => a.id !== id) }));
  }

  function cambiarCampo(ruta: string, texto: string) {
    cambiar((g) => ({
      ...g,
      valores: { ...g.valores, [ruta]: texto },
      camposTocados:
        campoDe(ruta)?.clase === "lista" && !g.camposTocados.includes(ruta)
          ? [...g.camposTocados, ruta]
          : g.camposTocados,
    }));
  }

  function quedarse(ruta: string, valor: unknown) {
    cambiarCampo(ruta, Array.isArray(valor) ? valor.map(String).join("\n") : String(valor));
  }

  function asumir(tipo: TipoDeContradiccion) {
    cambiar((g) => (g.asumidas.includes(tipo) ? g : { ...g, asumidas: [...g.asumidas, tipo] }));
  }

  function deshacer(tipo: TipoDeContradiccion) {
    cambiar((g) => ({ ...g, asumidas: g.asumidas.filter((t) => t !== tipo) }));
  }

  function empezarDeCero() {
    descartar();
    setPasada(null);
    setFallido(null);
    setConfirmando(null);
  }

  const senaladas = new Set<string>([
    ...(pasada?.faltan ?? []),
    ...(pasada?.no_validos ?? []),
    ...(fallido?.fallo.tipo === "rechazo" ? fallido.fallo.campos.map(rutaEnLaFicha) : []),
  ]);

  return (
    <>
      <Cabecera pantalla="Encargo" />
      <main className="pagina encargo">
        <header className="encargo__cabecera">
          <span className="encargo__antetitulo">Nuevo encargo</span>
          <h1 className="encargo__titulo">Encarga una novela</h1>
          <p className="encargo__entradilla">
            Cuéntale al Entrevistador para quién es y qué te gustaría. Él completa la ficha, y un equipo de agentes
            escribe la novela capítulo a capítulo.
          </p>
        </header>

        {origen === "recuperado" && pasada === null && (
          <p className="nota">Tu encargo está guardado. Envía para ver qué entiende el sistema.</p>
        )}
        {origen === "ilegible" && (
          <p className="nota nota--aviso">
            No se ha podido recuperar el borrador anterior. Puedes empezar uno nuevo.
          </p>
        )}
        {!sePuedeGuardar && (
          <p className="nota nota--aviso">
            Este navegador no deja guardar el encargo: si recargas la página, perderás lo escrito.
          </p>
        )}

        <div className="encargo__columnas">
          <div className="encargo__izquierda">
            <Conversacion
              aportaciones={guardado.aportaciones}
              bloqueado={enviando}
              alQuitar={quitar}
              alPegar={pegar}
              alEnviar={enviar}
            />

            {enviando && (
              <Espera que="El Entrevistador está leyendo tu encargo. Puede tardar un par de minutos" />
            )}

            {fallido && (
              <AccionesDelFallo
                fallido={fallido}
                reintentar={() => void mandar(fallido.cuerpo, guardado.idEntrevista)}
                empezarConLoQueLlevo={() => {
                  cambiar((g) => ({ ...g, idEntrevista: null }));
                  setFallido(null);
                  setPasada(null);
                }}
                empezarNuevo={() => setConfirmando("empezar_nuevo")}
              />
            )}

            {pasada && !enviando && (
              <Resultado
                pasada={pasada}
                asumidas={guardado.asumidas}
                bloqueado={enviando}
                alAsumir={asumir}
                alDeshacer={deshacer}
              />
            )}
          </div>

          <FichaDelEncargo
            valores={guardado.valores}
            propuesto={pasada?.brief_propuesto ?? null}
            senaladas={senaladas}
            bloqueado={enviando}
            alCambiar={cambiarCampo}
            alQuedarse={quedarse}
          />
        </div>

        <footer className="encargo__pie">
          {confirmando === null ? (
            <button
              type="button"
              className="discreto"
              disabled={enviando}
              onClick={() => setConfirmando("descartar")}
            >
              Descartar este encargo
            </button>
          ) : (
            <div className="confirmar" role="alertdialog" aria-label="Confirmar">
              <p>
                {confirmando === "descartar"
                  ? "¿Seguro que quieres descartar este encargo? Se borra todo lo escrito y pegado."
                  : "Se descarta este encargo para empezar uno nuevo. Se borra todo lo escrito y pegado."}
              </p>
              <button type="button" className="principal" onClick={empezarDeCero}>
                Sí, descartarlo
              </button>
              <button type="button" onClick={() => setConfirmando(null)}>
                No, conservarlo
              </button>
            </div>
          )}
        </footer>
      </main>
    </>
  );
}

type AccionesProps = {
  fallido: EnvioFallido;
  reintentar: () => void;
  empezarConLoQueLlevo: () => void;
  empezarNuevo: () => void;
};

// Qué se ofrece según lo que devolvió el servidor. En ninguno de los casos se
// pierde nada de lo escrito (SPEC2 RF-08, RF-60 a RF-62).
function AccionesDelFallo({ fallido, reintentar, empezarConLoQueLlevo, empezarNuevo }: AccionesProps) {
  const { fallo } = fallido;
  if (fallo.tipo === "sin_servidor" || fallo.estado === 502) {
    return <AvisoDeFallo fallo={fallo} reintentar={reintentar} />;
  }
  if (fallo.estado === 404) {
    return (
      <AvisoDeFallo fallo={fallo}>
        <button type="button" onClick={empezarConLoQueLlevo}>
          Empezar de nuevo con lo que llevo
        </button>
      </AvisoDeFallo>
    );
  }
  if (fallo.estado === 409) {
    return (
      <AvisoDeFallo fallo={fallo}>
        <button type="button" onClick={empezarNuevo}>
          Empezar un encargo nuevo
        </button>
      </AvisoDeFallo>
    );
  }
  if (fallo.estado === 422 && fallo.campos.length === 0) {
    return (
      <AvisoDeFallo fallo={fallo}>
        <span>Puedes quitar algún texto pegado y volver a enviar.</span>
      </AvisoDeFallo>
    );
  }
  return <AvisoDeFallo fallo={fallo} />;
}
