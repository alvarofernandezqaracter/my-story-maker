// SPEC2 RI-02 y OBJ-05: el mismo trato que el backend se da con RNF-09. Se
// genera el cliente desde backend/openapi.yaml y se compara con lo commiteado;
// si difiere, se reescribe y la prueba falla una vez, para que el movimiento
// de la frontera aparezca en el diff junto al cambio que lo movió.
// @vitest-environment node
import { readFile, writeFile } from "node:fs/promises";
import { expect, it } from "vitest";
import { DESTINO, generar } from "../scripts/generar-contrato.mjs";

it("el cliente generado coincide con backend/openapi.yaml", async () => {
  const esperado = await generar();
  // Git puede sacar el fichero con saltos CRLF en Windows: el contenido es el
  // mismo y no cuenta como cambio del borde.
  const leido = await readFile(DESTINO, "utf-8").catch(() => "");
  const coincide = leido.replace(/\r\n/g, "\n") === esperado;
  if (!coincide) await writeFile(DESTINO, esperado);
  expect(
    coincide,
    "esquema.d.ts no coincidía con backend/openapi.yaml: se ha regenerado. Revisa el diff y commitéalo con el cambio del borde.",
  ).toBe(true);
});
