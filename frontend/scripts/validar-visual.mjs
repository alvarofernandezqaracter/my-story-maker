// El validador visual de la lectura (SPEC2 RF-78, RF-79, D-24).
//
//   npm run validar-visual
//
// Levanta un backend de prueba sembrado con el ejecutor fingido —no gasta—, la
// interfaz con Vite apuntando a él, y abre la lectura en Chromium sin cabeza a
// dos anchos. Coteja lo que la página enseña con lo que la API sirve: portada,
// índice y ficha de personajes y lugares. Cada fallo sale como una línea JSON
// con a quién vuelve —`frontend` si la API lo servía y la página no lo enseña,
// `backend` si la API no lo servía— y la orden termina con código 1. No escribe
// nada en disco.
//
// Usa el paquete `playwright` en la misma versión que el servidor MCP de
// `.claude/mcp.json`, así que el Chromium que instala la orden de CLAUDE.md
// sirve a los dos. El Python del backend es el de backend/.venv, o el que diga
// NOVELA_PYTHON.
//
// VALIDAR_ROMPER=portada esconde la portada a propósito, para ver que el
// validador lo caza.

// Lo que va dentro de `pagina.evaluate` corre en el navegador, no en Node.
/* global document, window */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer as servidorDePrueba } from "node:net";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const BACKEND = fileURLToPath(new URL("../../backend/", import.meta.url));
const FRONTEND = fileURLToPath(new URL("../", import.meta.url));
const PYTHON =
  process.env.NOVELA_PYTHON ??
  [".venv/Scripts/python.exe", ".venv/bin/python"].map((r) => BACKEND + r).find((r) => existsSync(r));
const ROMPER = process.env.VALIDAR_ROMPER ?? "";

const ANCHOS = [
  { ancho: "escritorio", width: 1280, height: 900 },
  { ancho: "movil", width: 390, height: 844 },
];

const TITULO_DEL_GRUPO = { Personaje: "Personajes", Lugar: "Lugares" };

function puertoLibre() {
  return new Promise((resolver, rechazar) => {
    const prueba = servidorDePrueba();
    prueba.once("error", rechazar);
    prueba.listen(0, "127.0.0.1", () => {
      const { port } = prueba.address();
      prueba.close(() => resolver(port));
    });
  });
}

function arrancarBackend(puerto) {
  return new Promise((resolver, rechazar) => {
    const hijo = spawn(PYTHON, ["tests/servidor_sembrado.py", "--puerto", String(puerto)], {
      cwd: BACKEND,
      stdio: ["pipe", "pipe", "inherit"],
    });
    const plazo = setTimeout(() => rechazar(new Error("el backend sembrado no contestó en 180 s")), 180_000);
    hijo.once("exit", (codigo) => rechazar(new Error(`el backend sembrado se paró (código ${codigo})`)));
    createInterface({ input: hijo.stdout }).on("line", (linea) => {
      try {
        const dicho = JSON.parse(linea);
        clearTimeout(plazo);
        if (dicho.error) rechazar(new Error(dicho.error));
        else resolver({ hijo, idObra: dicho.id_obra });
      } catch {
        // Lo que no es JSON es ruido del servidor: no se interpreta.
      }
    });
  });
}

async function pedir(puerto, ruta) {
  const respuesta = await fetch(`http://127.0.0.1:${puerto}${ruta}`);
  if (!respuesta.ok) throw new Error(`${ruta}: ${respuesta.status}`);
  return respuesta.json();
}

const fallos = [];
let comprobaciones = 0;

function comprobar(comprobacion, ancho, bien, detalle, vuelveA = "frontend") {
  comprobaciones += 1;
  if (!bien) {
    const fallo = { validador: "visual", comprobacion, ancho, detalle, vuelve_a: vuelveA };
    fallos.push(fallo);
    console.log(JSON.stringify(fallo));
  }
}

async function seVe(localizador) {
  if ((await localizador.count()) === 0) return false;
  const primero = localizador.first();
  if (!(await primero.isVisible())) return false;
  const caja = await primero.boundingBox();
  return caja !== null && caja.width > 0 && caja.height > 0;
}

/** El capítulo queda a la vista tras pulsar su enlace: su cabeza cae en la mitad de arriba. */
async function capituloALaVista(pagina, numero) {
  await pagina.waitForTimeout(300);
  return pagina.evaluate((n) => {
    const capitulo = document.getElementById(`capitulo-${n}`);
    if (!capitulo) return false;
    const { top } = capitulo.getBoundingClientRect();
    return top > -8 && top < window.innerHeight / 2;
  }, numero);
}

async function validarAncho(navegador, base, datos, { ancho, width, height }) {
  const { ficha, manuscrito, hechos, idObra } = datos;
  const contexto = await navegador.newContext({ viewport: { width, height }, locale: "es-ES" });
  const pagina = await contexto.newPage();
  await pagina.goto(`${base}/obras/${idObra}/manuscrito`);
  const portada = pagina.getByRole("region", { name: "Portada" });
  try {
    await portada.waitFor({ state: "attached", timeout: 20_000 });
  } catch {
    comprobar("portada", ancho, false, "la lectura no llegó a pintar la portada");
    await contexto.close();
    return;
  }
  if (ROMPER === "portada") await pagina.addStyleTag({ content: ".portada { display: none !important; }" });

  // Portada: el título y, con destinatario, para quién y la dedicatoria.
  comprobar("portada", ancho, Boolean(ficha.titulo), "la ficha no trae título", "backend");
  comprobar(
    "portada",
    ancho,
    Boolean(ficha.dedicatoria && ficha.destinatario),
    "la ficha de una obra con destinatario no trae el destinatario o la dedicatoria",
    "backend",
  );
  const titulo = portada.getByRole("heading", { level: 1 });
  comprobar(
    "portada",
    ancho,
    (await seVe(titulo)) && (await titulo.innerText()).trim() === ficha.titulo,
    `el título «${ficha.titulo}» no se ve en la portada`,
  );
  if (ficha.dedicatoria) {
    const dedicatoria = portada.getByLabel("Dedicatoria");
    comprobar(
      "portada",
      ancho,
      (await seVe(dedicatoria)) && (await dedicatoria.innerText()).trim() === ficha.dedicatoria,
      "la dedicatoria que sirve la ficha no se ve en la portada",
    );
  }
  if (ficha.destinatario) {
    comprobar(
      "portada",
      ancho,
      await seVe(portada.getByText(`Para ${ficha.destinatario}`, { exact: true })),
      `«Para ${ficha.destinatario}» no se ve en la portada`,
    );
  }

  // Índice: un enlace por capítulo servido, y pulsarlo lleva a él.
  const capitulos = [...new Set(manuscrito.unidades.map((u) => u.capitulo))];
  comprobar("indice", ancho, capitulos.length > 0, "el manuscrito no trae ningún capítulo", "backend");
  const enlaces = pagina.getByRole("navigation", { name: "Índice de capítulos" }).getByRole("link");
  const enIndice = await enlaces.count();
  comprobar(
    "indice",
    ancho,
    enIndice === capitulos.length,
    `el índice enseña ${enIndice} enlaces y el manuscrito trae ${capitulos.length} capítulos`,
  );
  for (const [i, numero] of capitulos.entries()) {
    const enlace = enlaces.nth(i);
    const visible = i < enIndice && (await seVe(enlace));
    comprobar("indice", ancho, visible, `el enlace al capítulo ${numero} no se ve`);
    if (!visible) continue;
    await enlace.click();
    comprobar("indice", ancho, await capituloALaVista(pagina, numero), `pulsar el capítulo ${numero} no lo deja a la vista`);
  }

  // Ficha: cada personaje y cada lugar, con un enlace por capítulo que lleva a él.
  const fichas = hechos.filter((h) => h.tipo in TITULO_DEL_GRUPO);
  comprobar("ficha", ancho, fichas.length > 0, "la biblia no trae personajes ni lugares", "backend");
  for (const hecho of fichas) {
    const grupo = pagina.getByRole("region", { name: TITULO_DEL_GRUPO[hecho.tipo] });
    const nombre = hecho.nombre ?? hecho.id;
    comprobar("ficha", ancho, await seVe(grupo.getByText(nombre, { exact: true })), `«${nombre}» no se ve en la ficha`);
    const suyos = grupo.getByRole("navigation", { name: `Capítulos de ${nombre}` }).getByRole("link");
    const cuantos = await suyos.count();
    comprobar(
      "ficha",
      ancho,
      cuantos === hecho.capitulos.length,
      `«${nombre}» enseña ${cuantos} enlaces y se usa en ${hecho.capitulos.length} capítulos`,
    );
    if (cuantos > 0 && hecho.capitulos.length > 0) {
      await suyos.first().click();
      comprobar(
        "ficha",
        ancho,
        await capituloALaVista(pagina, hecho.capitulos[0]),
        `el enlace de «${nombre}» al capítulo ${hecho.capitulos[0]} no lo deja a la vista`,
      );
    }
  }

  // Nada se sale de ancho: una lectura con barra horizontal no se ve bien.
  const sobra = await pagina.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  comprobar("ancho", ancho, sobra <= 1, `la página se sale ${sobra} px de ancho`);
  await contexto.close();
}

async function main() {
  if (!PYTHON) {
    console.error("[validar-visual] No encuentro backend/.venv ni NOVELA_PYTHON: créalo siguiendo CLAUDE.md.");
    return 2;
  }
  const [puertoBackend, puertoVite] = [await puertoLibre(), await puertoLibre()];
  let backend = null;
  let vite = null;
  let navegador = null;
  try {
    const arrancado = await arrancarBackend(puertoBackend);
    backend = arrancado.hijo;
    const idObra = arrancado.idObra;
    const [ficha, manuscrito, hechos] = await Promise.all([
      pedir(puertoBackend, `/obras/${idObra}`),
      pedir(puertoBackend, `/obras/${idObra}/manuscrito`),
      pedir(puertoBackend, `/obras/${idObra}/hechos`),
    ]);

    const { createServer } = await import("vite");
    vite = await createServer({
      root: FRONTEND,
      logLevel: "error",
      server: {
        host: "127.0.0.1",
        port: puertoVite,
        strictPort: true,
        proxy: {
          "/api": {
            target: `http://127.0.0.1:${puertoBackend}`,
            changeOrigin: true,
            rewrite: (ruta) => ruta.replace(/^\/api/, ""),
          },
        },
      },
    });
    await vite.listen();

    const { chromium } = await import("playwright");
    navegador = await chromium.launch({ headless: true });
    for (const ancho of ANCHOS) {
      await validarAncho(navegador, `http://127.0.0.1:${puertoVite}`, { ficha, manuscrito, hechos, idObra }, ancho);
    }
  } finally {
    await navegador?.close();
    await vite?.close();
    if (backend && backend.exitCode === null) {
      backend.stdin.end();
      await new Promise((resolver) => {
        const plazo = setTimeout(() => {
          backend.kill();
          resolver();
        }, 8000);
        backend.once("exit", () => {
          clearTimeout(plazo);
          resolver();
        });
      });
    }
  }
  console.log(JSON.stringify({ validador: "visual", pasa: fallos.length === 0, comprobaciones, fallos: fallos.length }));
  return fallos.length === 0 ? 0 : 1;
}

main().then(
  (codigo) => process.exit(codigo),
  (error) => {
    console.error(`[validar-visual] ${error.message}`);
    process.exit(2);
  },
);
