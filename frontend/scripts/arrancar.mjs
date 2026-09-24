// Pone la interfaz en pie con una sola orden (SPEC2 RNF-06): arranca el backend
// si el puerto 8000 no responde ya, y después Vite. Al cerrar, apaga lo que haya
// arrancado él.
//
//   node scripts/arrancar.mjs dev       servidor de desarrollo (npm run dev)
//   node scripts/arrancar.mjs preview   sirve dist/ ya construido (npm start)
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const modo = process.argv[2] === "preview" ? "preview" : "dev";
const BACKEND = fileURLToPath(new URL("../../backend/", import.meta.url));
const FRONTEND = fileURLToPath(new URL("../", import.meta.url));
const PUERTO = 8000;
// El Python del entorno: Scripts/ en Windows, bin/ en Linux o macOS.
const PYTHON = [".venv/Scripts/python.exe", ".venv/bin/python"]
  .map((relativa) => BACKEND + relativa)
  .find((ruta) => existsSync(ruta));

async function backendResponde() {
  try {
    const respuesta = await fetch(`http://127.0.0.1:${PUERTO}/openapi.json`, {
      signal: AbortSignal.timeout(1500),
    });
    return respuesta.ok;
  } catch {
    return false;
  }
}

const hijos = [];

function apagar(codigo = 0) {
  for (const hijo of hijos) {
    if (hijo.exitCode === null) hijo.kill();
  }
  process.exit(codigo);
}

process.on("SIGINT", () => apagar(0));
process.on("SIGTERM", () => apagar(0));

if (await backendResponde()) {
  console.log(`[arrancar] El backend ya responde en el puerto ${PUERTO}: se usa ese.`);
} else if (!PYTHON) {
  console.error(
    "[arrancar] No encuentro backend/.venv. Créalo una vez siguiendo CLAUDE.md " +
      "(«Cómo se trabaja con el backend»). Arranco solo la interfaz: dirá que no hay servidor.",
  );
} else {
  console.log(
    "[arrancar] Arranco el backend. Ojo: al arrancar relanza sola cualquier obra que se " +
      "quedara a medias (SPEC1 D-33), y eso gasta.",
  );
  const backend = spawn(
    PYTHON,
    ["-m", "uvicorn", "novela.api.principal:app", "--host", "127.0.0.1", "--port", String(PUERTO)],
    { cwd: BACKEND, stdio: "inherit" },
  );
  hijos.push(backend);
  backend.on("exit", (codigo) => {
    if (codigo !== null && codigo !== 0) {
      console.error(`[arrancar] El backend se ha parado (código ${codigo}). La interfaz lo dirá en pantalla.`);
    }
  });
}

const VITE = fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
const vite = spawn(process.execPath, modo === "dev" ? [VITE] : [VITE, "preview"], {
  cwd: FRONTEND,
  stdio: "inherit",
});
hijos.push(vite);
vite.on("exit", (codigo) => apagar(codigo ?? 0));
