// Genera src/compartido/api/esquema.d.ts desde backend/openapi.yaml.
// Es la única forma de producir ese fichero: la orden (`npm run contrato`,
// y `predev`/`prebuild`) y la prueba del contrato llaman a la misma función,
// así que dan exactamente lo mismo (SPEC2 RI-02).
import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

export const CONTRATO = new URL("../../backend/openapi.yaml", import.meta.url);
export const DESTINO = new URL("../src/compartido/api/esquema.d.ts", import.meta.url);
const CABECERA =
  "// GENERADO desde backend/openapi.yaml por scripts/generar-contrato.mjs.\n" +
  "// No se edita a mano: si el borde cambia, se regenera (SPEC2 RI-02).\n";

export async function generar(contrato = CONTRATO) {
  return CABECERA + astToString(await openapiTS(contrato));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await writeFile(DESTINO, await generar());
  console.log("Contrato regenerado:", fileURLToPath(DESTINO));
}
