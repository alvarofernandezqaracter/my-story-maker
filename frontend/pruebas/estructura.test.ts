// Lo que ESLint no ve (SPEC2 RI-01, RNF-03): no hay capa de dominio en el
// cliente y solo un fichero habla con openapi-fetch.
// @vitest-environment node
import { readdir, readFile } from "node:fs/promises";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

async function recorrer(carpeta: string): Promise<{ carpetas: string[]; ficheros: string[] }> {
  const carpetas: string[] = [];
  const ficheros: string[] = [];
  for (const entrada of await readdir(carpeta, { withFileTypes: true })) {
    const ruta = join(carpeta, entrada.name);
    if (entrada.isDirectory()) {
      carpetas.push(ruta);
      const dentro = await recorrer(ruta);
      carpetas.push(...dentro.carpetas);
      ficheros.push(...dentro.ficheros);
    } else {
      ficheros.push(ruta);
    }
  }
  return { carpetas, ficheros };
}

const comoRuta = (ruta: string) => relative(SRC, ruta).split(sep).join("/");

it("no existe ninguna carpeta services, models ni domain bajo src/", async () => {
  const { carpetas } = await recorrer(SRC);
  const prohibidas = carpetas.filter((c) => /^(services|models|domain)$/i.test(c.split(sep).at(-1) ?? ""));
  expect(prohibidas.map(comoRuta)).toEqual([]);
});

it("el único fichero que importa openapi-fetch es compartido/api/cliente.ts", async () => {
  const { ficheros } = await recorrer(SRC);
  const importan: string[] = [];
  for (const fichero of ficheros.filter((f) => /\.(ts|tsx)$/.test(f))) {
    if (/from\s+["']openapi-fetch["']/.test(await readFile(fichero, "utf-8"))) importan.push(comoRuta(fichero));
  }
  expect(importan).toEqual(["compartido/api/cliente.ts"]);
});

it("el almacenamiento del navegador solo aparece en almacen-local.ts (SPEC2 RD-01, RD-02)", async () => {
  const { ficheros } = await recorrer(SRC);
  const usan: string[] = [];
  for (const fichero of ficheros.filter((f) => /\.(ts|tsx)$/.test(f))) {
    if (/localStorage|sessionStorage|indexedDB/.test(await readFile(fichero, "utf-8"))) usan.push(comoRuta(fichero));
  }
  expect(usan).toEqual(["compartido/almacen-local.ts"]);
});
