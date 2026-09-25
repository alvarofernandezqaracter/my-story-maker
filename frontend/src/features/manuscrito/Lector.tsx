import { Fragment, useEffect, useRef, useState, type CSSProperties } from "react";
import { Icono } from "../../compartido/componentes/Icono";
import { esNumeroEntre, esUnoDe, guardarPreferencia, seVeOscuro, usePreferencia } from "../../compartido/preferencias";
import type { CapituloLeido } from "./agrupar";
import {
  contarCoincidencias,
  minutosDeLectura,
  palabrasDe,
  patronDeBusqueda,
  romano,
  trocear,
} from "./herramientas";

const TEMAS_DE_LECTURA = ["papel", "sepia", "noche"] as const;
type TemaDeLectura = (typeof TEMAS_DE_LECTURA)[number];
const NOMBRE_DEL_TEMA: Record<TemaDeLectura, string> = { papel: "Papel", sepia: "Sepia", noche: "Noche" };

const LETRAS = ["serif", "sans"] as const;
type Letra = (typeof LETRAS)[number];

const ANCHOS = ["estrecho", "normal", "amplio"] as const;
type Ancho = (typeof ANCHOS)[number];
const NOMBRE_DEL_ANCHO: Record<Ancho, string> = { estrecho: "Estrecho", normal: "Normal", amplio: "Amplio" };

const TAMANOS = [0.95, 1.05, 1.15, 1.28, 1.42, 1.58];

type Props = {
  idObra: string;
  capitulos: CapituloLeido[];
  cambiados: Set<number>;
  base: number | null | undefined;
  para: string | null | undefined;
  dedicatoria: string | null | undefined;
  enlaceDelPdf: string;
  alVolverALaPortada: () => void;
};

export const claveDeLaPosicion = (idObra: string) => `lectura:${idObra}`;

function escribiendo(objetivo: EventTarget | null): boolean {
  return objetivo instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(objetivo.tagName);
}

// El libro abierto: índice, texto y herramientas del lector. Lo que el lector
// elige —letra, tema, ancho— es suyo y se recuerda en su navegador.
export function Lector(props: Props) {
  const { idObra, capitulos, cambiados, base, para, dedicatoria, enlaceDelPdf, alVolverALaPortada } = props;
  const [tamano, setTamano] = usePreferencia("lectura-tamano", 2, esNumeroEntre(0, TAMANOS.length - 1));
  const [tema, setTema] = usePreferencia<TemaDeLectura>(
    "lectura-tema",
    seVeOscuro() ? "noche" : "papel",
    esUnoDe(TEMAS_DE_LECTURA),
  );
  const [letra, setLetra] = usePreferencia<Letra>("lectura-letra", "serif", esUnoDe(LETRAS));
  const [ancho, setAncho] = usePreferencia<Ancho>("lectura-ancho", "normal", esUnoDe(ANCHOS));
  const [activo, setActivo] = useState<number | null>(null);
  const [progreso, setProgreso] = useState(0);
  const [inmersivo, setInmersivo] = useState(false);
  const [ajustes, setAjustes] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [actual, setActual] = useState(0);
  const texto = useRef<HTMLDivElement>(null);
  const envoltorioDeAjustes = useRef<HTMLDivElement>(null);
  const campoDeBusqueda = useRef<HTMLInputElement>(null);

  const patron = patronDeBusqueda(busqueda);
  const total = contarCoincidencias(capitulos, patron);

  // Qué capítulo se está leyendo y cuánto va leído, al ritmo del scroll.
  useEffect(() => {
    let pendiente = false;
    function medir() {
      pendiente = false;
      const caja = texto.current;
      if (!caja) return;
      const rect = caja.getBoundingClientRect();
      const alto = rect.height - window.innerHeight * 0.6;
      setProgreso(alto > 0 ? Math.min(1, Math.max(0, -rect.top / alto)) : 0);
      let visto: number | null = null;
      for (const articulo of caja.querySelectorAll<HTMLElement>("article.capitulo")) {
        if (articulo.getBoundingClientRect().top <= window.innerHeight * 0.35) {
          visto = Number(articulo.dataset.capitulo);
        }
      }
      setActivo(visto);
    }
    function alDesplazar() {
      if (!pendiente) {
        pendiente = true;
        requestAnimationFrame(medir);
      }
    }
    medir();
    window.addEventListener("scroll", alDesplazar, { passive: true });
    window.addEventListener("resize", alDesplazar);
    return () => {
      window.removeEventListener("scroll", alDesplazar);
      window.removeEventListener("resize", alDesplazar);
    };
  }, []);

  useEffect(() => {
    if (activo !== null) guardarPreferencia(claveDeLaPosicion(idObra), activo);
  }, [activo, idObra]);

  // El modo sin distracciones esconde la barra y el lateral de la aplicación.
  useEffect(() => {
    document.body.classList.toggle("lectura-inmersiva", inmersivo);
    return () => document.body.classList.remove("lectura-inmersiva");
  }, [inmersivo]);

  // Los ajustes se cierran al pulsar fuera de ellos.
  useEffect(() => {
    if (!ajustes) return;
    function alPulsarFuera(evento: PointerEvent) {
      if (!envoltorioDeAjustes.current?.contains(evento.target as Node)) setAjustes(false);
    }
    document.addEventListener("pointerdown", alPulsarFuera);
    return () => document.removeEventListener("pointerdown", alPulsarFuera);
  }, [ajustes]);

  // La coincidencia en curso se marca y se trae a la vista.
  useEffect(() => {
    const caja = texto.current;
    if (!caja) return;
    const marcas = caja.querySelectorAll<HTMLElement>("mark.coincidencia");
    marcas.forEach((m) => m.classList.remove("activa"));
    const marca = marcas[actual];
    if (marca) {
      marca.classList.add("activa");
      marca.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [actual, busqueda]);

  function irA(capitulo: number) {
    document.getElementById(`capitulo-${capitulo}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const posicion = activo === null ? -1 : capitulos.findIndex((c) => c.capitulo === activo);

  useEffect(() => {
    function alPulsar(evento: KeyboardEvent) {
      if (evento.metaKey || evento.ctrlKey || evento.altKey) return;
      if (evento.key === "Escape") {
        setAjustes(false);
        setInmersivo(false);
        return;
      }
      if (escribiendo(evento.target)) return;
      if (evento.key === "/") {
        evento.preventDefault();
        campoDeBusqueda.current?.focus();
      } else if (evento.key === "ArrowRight") {
        const siguiente = capitulos[posicion + 1];
        if (siguiente) irA(siguiente.capitulo);
      } else if (evento.key === "ArrowLeft") {
        const anterior = capitulos[posicion - 1];
        if (anterior) irA(anterior.capitulo);
      }
    }
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  });

  function saltar(paso: number) {
    if (total === 0) return;
    setActual((a) => (a + paso + total) % total);
  }

  const leyendo = posicion >= 0 ? capitulos[posicion] : undefined;

  return (
    <div
      className="lector"
      id="lector"
      data-tema-lectura={tema}
      data-letra={letra}
      data-ancho={ancho}
      style={{ "--tamano-lectura": `${TAMANOS[tamano]}rem` } as CSSProperties}
    >
      <div className="lector__progreso" aria-hidden="true">
        <span style={{ transform: `scaleX(${progreso})` }} />
      </div>

      <div className="lector__barra" role="toolbar" aria-label="Herramientas de lectura">
        <button
          type="button"
          className="boton-icono lector__boton-indice"
          aria-label="Índice"
          onClick={() => document.getElementById("indice")?.scrollIntoView({ behavior: "smooth", block: "center" })}
        >
          <Icono nombre="indice" />
        </button>
        <span className="lector__donde" aria-live="polite">
          {leyendo ? (
            <>
              <strong>Capítulo {romano(leyendo.capitulo)}</strong>
              <span>{Math.round(progreso * 100)} % leído</span>
            </>
          ) : (
            <>
              <strong>{capitulos.length} capítulos</strong>
              <span>Listo para leer</span>
            </>
          )}
        </span>

        <label className="lector__busqueda">
          <Icono nombre="buscar" tamano={16} />
          <span className="visualmente-oculto">Buscar en la novela</span>
          <input
            ref={campoDeBusqueda}
            type="search"
            placeholder="Buscar en la novela"
            value={busqueda}
            onChange={(e) => {
              setBusqueda(e.target.value);
              setActual(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                saltar(e.shiftKey ? -1 : 1);
              }
            }}
          />
          {patron && (
            <span className="lector__coincidencias" aria-live="polite">
              {total === 0 ? "Sin resultados" : `${actual + 1} de ${total}`}
            </span>
          )}
          {patron && total > 1 && (
            <span className="lector__saltos">
              <button type="button" className="boton-icono" aria-label="Coincidencia anterior" onClick={() => saltar(-1)}>
                <Icono nombre="arriba" tamano={15} />
              </button>
              <button type="button" className="boton-icono" aria-label="Coincidencia siguiente" onClick={() => saltar(1)}>
                <Icono nombre="abajo" tamano={15} />
              </button>
            </span>
          )}
        </label>

        <div className="lector__herramientas">
          <div className="lector__ajustes-envoltorio" ref={envoltorioDeAjustes}>
            <button
              type="button"
              className="boton-icono"
              aria-label="Ajustes de lectura"
              aria-expanded={ajustes}
              onClick={() => setAjustes((v) => !v)}
            >
              <Icono nombre="letra" />
            </button>
            {ajustes && (
              <div className="lector__ajustes" role="dialog" aria-label="Ajustes de lectura">
                <div className="ajuste">
                  <span className="ajuste__nombre">Tamaño</span>
                  <div className="ajuste__tamano">
                    <button
                      type="button"
                      aria-label="Letra más pequeña"
                      disabled={tamano === 0}
                      onClick={() => setTamano(tamano - 1)}
                    >
                      A−
                    </button>
                    <span className="ajuste__puntos" aria-hidden="true">
                      {TAMANOS.map((_, i) => (
                        <span key={i} data-activo={i <= tamano} />
                      ))}
                    </span>
                    <button
                      type="button"
                      aria-label="Letra más grande"
                      disabled={tamano === TAMANOS.length - 1}
                      onClick={() => setTamano(tamano + 1)}
                    >
                      A+
                    </button>
                  </div>
                </div>
                <div className="ajuste">
                  <span className="ajuste__nombre">Fondo</span>
                  <div className="ajuste__opciones">
                    {TEMAS_DE_LECTURA.map((t) => (
                      <button
                        key={t}
                        type="button"
                        className="ajuste__muestra"
                        data-muestra={t}
                        aria-pressed={tema === t}
                        onClick={() => setTema(t)}
                      >
                        {NOMBRE_DEL_TEMA[t]}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="ajuste">
                  <span className="ajuste__nombre">Letra</span>
                  <div className="ajuste__opciones">
                    <button type="button" className="ajuste__letra ajuste__letra--serif" aria-pressed={letra === "serif"} onClick={() => setLetra("serif")}>
                      Clásica
                    </button>
                    <button type="button" className="ajuste__letra ajuste__letra--sans" aria-pressed={letra === "sans"} onClick={() => setLetra("sans")}>
                      Moderna
                    </button>
                  </div>
                </div>
                <div className="ajuste">
                  <span className="ajuste__nombre">Ancho</span>
                  <div className="ajuste__opciones">
                    {ANCHOS.map((a) => (
                      <button key={a} type="button" aria-pressed={ancho === a} onClick={() => setAncho(a)}>
                        {NOMBRE_DEL_ANCHO[a]}
                      </button>
                    ))}
                  </div>
                </div>
                <p className="ajuste__atajos">
                  Atajos: <kbd>←</kbd> <kbd>→</kbd> cambian de capítulo · <kbd>/</kbd> busca · <kbd>Esc</kbd> cierra
                </p>
                <button type="button" className="principal ajuste__listo" onClick={() => setAjustes(false)}>
                  Listo
                </button>
              </div>
            )}
          </div>
          <button
            type="button"
            className="boton-icono"
            aria-label={inmersivo ? "Salir del modo sin distracciones" : "Modo sin distracciones"}
            aria-pressed={inmersivo}
            onClick={() => {
              const donde = activo;
              setInmersivo((v) => !v);
              // Al quitar o poner la portada el texto se mueve: se vuelve al capítulo que se leía.
              requestAnimationFrame(() => {
                if (donde !== null) document.getElementById(`capitulo-${donde}`)?.scrollIntoView({ block: "start" });
                else document.getElementById("lector")?.scrollIntoView({ block: "start" });
              });
            }}
          >
            <Icono nombre={inmersivo ? "contraer" : "expandir"} />
          </button>
          <a className="boton boton-icono" href={enlaceDelPdf} download aria-label="Descargar en PDF" title="Descargar en PDF">
            <Icono nombre="descarga" />
          </a>
        </div>
      </div>

      <div className="lector__cuerpo">
        <nav className="indice" id="indice" aria-label="Índice de capítulos">
          <p className="indice__titulo">Índice</p>
          <ol>
            {capitulos.map((c) => (
              <li key={c.capitulo} data-activo={c.capitulo === activo}>
                <a href={`#capitulo-${c.capitulo}`}>
                  <span className="indice__numero">{romano(c.capitulo)}</span>
                  <span className="indice__nombre">
                    Capítulo {c.capitulo}
                    {cambiados.has(c.capitulo) && <span className="indice__cambio"> · cambió</span>}
                  </span>
                  <span className="indice__minutos">{minutosDeLectura(palabrasDe(c))} min</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="texto" ref={texto}>
          {capitulos.map((capitulo, i) => (
            <Capitulo
              key={capitulo.capitulo}
              capitulo={capitulo}
              anterior={capitulos[i - 1]}
              siguiente={capitulos[i + 1]}
              cambiado={cambiados.has(capitulo.capitulo)}
              base={base}
              patron={patron}
            />
          ))}
          <footer className="colofon">
            <span className="colofon__fin">Fin</span>
            <span className="colofon__ornamento" aria-hidden="true">
              ❦
            </span>
            {para && <p className="colofon__para">Escrita para {para}</p>}
            {dedicatoria && <p className="colofon__dedicatoria">«{dedicatoria}»</p>}
            <div className="colofon__acciones">
              <a className="boton principal" href={enlaceDelPdf} download aria-label="Descargar el libro en PDF">
                <Icono nombre="descarga" /> Descargar el libro
              </a>
              <button type="button" onClick={alVolverALaPortada}>
                <Icono nombre="arriba" /> Volver a la portada
              </button>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}

type PropsDeCapitulo = {
  capitulo: CapituloLeido;
  anterior: CapituloLeido | undefined;
  siguiente: CapituloLeido | undefined;
  cambiado: boolean;
  base: number | null | undefined;
  patron: RegExp | null;
};

function Capitulo({ capitulo, anterior, siguiente, cambiado, base, patron }: PropsDeCapitulo) {
  const minutos = minutosDeLectura(palabrasDe(capitulo));
  return (
    <article
      id={`capitulo-${capitulo.capitulo}`}
      className="capitulo"
      data-capitulo={capitulo.capitulo}
      data-cambiado={cambiado}
    >
      <header className="capitulo__cabecera">
        <span className="capitulo__etiqueta">Capítulo</span>
        <h2 className="capitulo__numero">
          <span className="visualmente-oculto">Capítulo {capitulo.capitulo}</span>
          <span aria-hidden="true">{romano(capitulo.capitulo)}</span>
        </h2>
        <span className="capitulo__ornamento" aria-hidden="true" />
        <span className="capitulo__minutos">
          <Icono nombre="reloj" tamano={13} /> {minutos} min de lectura
        </span>
      </header>
      {cambiado && <p className="capitulo__cambio">Reescrito en esta versión respecto de la {base}.</p>}
      {capitulo.escenas.map((escena, j) => (
        <Fragment key={escena.escena + j}>
          {j > 0 && (
            <p className="separador" aria-hidden="true">
              ⁂
            </p>
          )}
          <section className="escena" aria-label={`Escena ${escena.escena}`}>
            {escena.parrafos.map((parrafo, k) => (
              <p key={k}>
                {patron === null
                  ? parrafo
                  : trocear(parrafo, patron).map((trozo, t) =>
                      trozo.coincide ? (
                        <mark key={t} className="coincidencia">
                          {trozo.texto}
                        </mark>
                      ) : (
                        <Fragment key={t}>{trozo.texto}</Fragment>
                      ),
                    )}
              </p>
            ))}
          </section>
        </Fragment>
      ))}
      <nav className="capitulo__navegacion" aria-label="Entre capítulos">
        {anterior ? (
          <a href={`#capitulo-${anterior.capitulo}`} className="capitulo__salto">
            <span>
              <Icono nombre="izquierda" tamano={14} /> Anterior
            </span>
            <strong>Capítulo {romano(anterior.capitulo)}</strong>
          </a>
        ) : (
          <span />
        )}
        {siguiente && (
          <a href={`#capitulo-${siguiente.capitulo}`} className="capitulo__salto capitulo__salto--siguiente">
            <span>
              Siguiente <Icono nombre="derecha" tamano={14} />
            </span>
            <strong>Capítulo {romano(siguiente.capitulo)}</strong>
          </a>
        )}
      </nav>
    </article>
  );
}
