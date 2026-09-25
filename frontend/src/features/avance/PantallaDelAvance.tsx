import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import type { EstadoDelFlujo } from "../../compartido/api/avance";
import { AvisoDeFallo } from "../../compartido/componentes/AvisoDeFallo";
import { Cabecera } from "../../compartido/componentes/Cabecera";
import { MenuDeObra } from "../../compartido/componentes/MenuDeObra";
import { Espera } from "../../compartido/componentes/Espera";
import { Icono } from "../../compartido/componentes/Icono";
import { Libro } from "../../compartido/componentes/Libro";
import { TareasAbiertas } from "./TareasAbiertas";
import { useAvance, type Situacion } from "./usar-avance";
import "./avance.css";

// El color de la etiqueta es el de la situación equivalente del taller.
const COLOR_DE_SITUACION: Record<Situacion, string> = {
  en_marcha: "en_produccion",
  detenida: "detenida",
  terminada: "terminada",
};

const SITUACION: Record<Situacion, string> = {
  en_marcha: "En marcha",
  detenida: "Detenida",
  terminada: "Terminada",
};

const formato = new Intl.NumberFormat("es-ES");

function Conexion({ estado, intentos, ultimaNoticia }: {
  estado: EstadoDelFlujo;
  intentos: number;
  ultimaNoticia: number | null;
}) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const reloj = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(reloj);
  }, []);
  if (estado === "en_directo") return <span className="conexion conexion--directo">En directo</span>;
  if (estado === "conectando") return <span className="conexion">Conectando…</span>;
  return (
    <span className="conexion conexion--cortada" role="status">
      Se ha cortado la conexión. Reconectando (intento {intentos})…
      {ultimaNoticia !== null && (
        <> Última noticia hace {Math.max(0, Math.round((ahora - ultimaNoticia) / 1000))} s.</>
      )}
    </span>
  );
}

// Lo que el servidor va empujando mientras la obra corre (SPEC2 §4.2). Los
// números se pintan tal como vienen (RF-25).
export function PantallaDelAvance() {
  const { idObra = "" } = useParams();
  const navegar = useNavigate();
  const avance = useAvance(idObra);
  const [pidiendoMotivo, setPidiendoMotivo] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [copiado, setCopiado] = useState(false);

  const { foto, falloDeCarga, situacion, conexion, orden } = avance;

  if (!foto) {
    return (
      <>
        <Cabecera pantalla="Avance" />
        <MenuDeObra idObra={idObra} />
        <main className="pagina">
          {falloDeCarga === null ? (
            <Espera que="Cargando la obra" />
          ) : falloDeCarga.tipo === "sin_servidor" ? (
            <AvisoDeFallo fallo={falloDeCarga} reintentar={avance.reintentarCarga}>
              <span>Lo vuelvo a intentar solo cada pocos segundos.</span>
            </AvisoDeFallo>
          ) : (
            <AvisoDeFallo fallo={falloDeCarga}>
              <Link to="/">Ir al taller</Link>
            </AvisoDeFallo>
          )}
        </main>
      </>
    );
  }

  const { ficha, progreso } = foto;
  const direccion = window.location.href;
  const cociente = progreso.techo > 0 ? progreso.tokens_de_entrada_concurrentes / progreso.techo : 0;

  async function copiar() {
    try {
      await navigator.clipboard.writeText(direccion);
      setCopiado(true);
    } catch {
      setCopiado(false);
    }
  }

  return (
    <>
      <Cabecera pantalla="Avance" />
      <MenuDeObra idObra={idObra} />
      <main className="pagina avance">
        <header className="avance__cabecera">
          <div className="avance__titular">
            <Libro titulo={ficha.titulo} tamano="mini" />
            <div>
              <span className="avance__antetitulo">Avance de la obra</span>
              <h1>{ficha.titulo}</h1>
            </div>
          </div>
          <div className="avance__estado">
            {situacion && (
              <span className={`situacion situacion--${situacion}`} data-situacion={COLOR_DE_SITUACION[situacion]}>
                {SITUACION[situacion]}
              </span>
            )}
            {conexion && situacion !== "terminada" && (
              <Conexion
                estado={conexion.estado}
                intentos={conexion.intentos}
                ultimaNoticia={avance.ultimaNoticia}
              />
            )}
          </div>
        </header>

        {situacion === "terminada" && (
          <section className="avance__terminada" aria-label="Obra terminada">
            <span className="avance__sello" aria-hidden="true">
              <Icono nombre="hecho" tamano={26} />
            </span>
            <div>
              <h2>La novela está terminada</h2>
              <p>Los {ficha.capitulos_cerrados} capítulos están escritos. Ya se puede leer de principio a fin.</p>
            </div>
          </section>
        )}

        <section className="avance__cifras" aria-label="Cifras de la obra">
          <div className="cifra">
            <span className="cifra__etiqueta">Capítulo en curso</span>
            <span className="cifra__valor" data-testid="capitulo-en-curso">
              {progreso.capitulo_en_curso ?? "Ningún capítulo abierto ahora mismo"}
            </span>
          </div>
          <div className="cifra">
            <span className="cifra__etiqueta">Capítulos cerrados</span>
            <span className="cifra__valor">{ficha.capitulos_cerrados}</span>
          </div>
          <div className="cifra cifra--ancha">
            <span className="cifra__etiqueta">Tokens de entrada a la vez</span>
            <span className="cifra__nota">Cuánto contexto usan ahora los agentes que trabajan en paralelo</span>
            <span className="cifra__valor" data-testid="tokens">
              {formato.format(progreso.tokens_de_entrada_concurrentes)} de {formato.format(progreso.techo)}
            </span>
            <span className="barra" aria-hidden="true">
              <span className="barra__relleno" style={{ width: `${Math.min(1, cociente) * 100}%` }} />
            </span>
          </div>
        </section>

        <section className="avance__tareas" aria-label="Tareas abiertas">
          <h2>Tareas abiertas</h2>
          <TareasAbiertas tareas={progreso.tareas_abiertas} />
        </section>

        {avance.falloDeOrden && <AvisoDeFallo fallo={avance.falloDeOrden} />}

        <section className="avance__acciones" aria-label="Acciones">
          <button
            type="button"
            className={situacion === "terminada" ? "principal" : undefined}
            onClick={() => void navegar(`/obras/${encodeURIComponent(idObra)}/manuscrito`)}
          >
            <Icono nombre="libro" />
            {situacion === "terminada" ? "Leer la novela" : "Leer lo que hay"}
          </button>
          {progreso.detenida ? (
            <button type="button" disabled={orden !== null} onClick={avance.reanudar}>
              {orden === "reanudando" ? "Reanudando…" : "Reanudar"}
            </button>
          ) : (
            situacion === "en_marcha" &&
            !pidiendoMotivo && (
              <button type="button" disabled={orden !== null} onClick={() => setPidiendoMotivo(true)}>
                {orden === "deteniendo" ? "Deteniendo…" : "Detener"}
              </button>
            )
          )}
        </section>

        {pidiendoMotivo && (
          <form
            className="detener tarjeta"
            aria-label="Detener la obra"
            onSubmit={(e) => {
              e.preventDefault();
              avance.detener(motivo);
              setPidiendoMotivo(false);
              setMotivo("");
            }}
          >
            <label htmlFor="motivo">¿Por qué la detienes? (opcional)</label>
            <input id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
            <div className="detener__botones">
              <button type="submit" className="principal">
                Detener la obra
              </button>
              <button type="button" onClick={() => setPidiendoMotivo(false)}>
                Cancelar
              </button>
            </div>
          </form>
        )}

        <footer className="avance__pie">
          <p>Para volver a esta obra, guarda esta dirección:</p>
          <div className="direccion">
            <code>{direccion}</code>
            <button type="button" onClick={() => void copiar()}>
              {copiado ? "Copiada" : "Copiar"}
            </button>
          </div>
        </footer>
      </main>
    </>
  );
}
