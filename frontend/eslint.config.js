// Reglas de fronteras (SPEC2 RI-01, RNF-01, RNF-02). Es la «regla de fronteras
// del linter» que pide docs/validators.md §6.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";

const FUNCIONALIDADES = ["encargo", "avance", "tareas", "manuscrito"];

// Nadie en src/ lee ficheros ni toca el backend por su cuenta (RNF-01).
const SIN_DISCO = [
  { name: "fs", message: "La interfaz no lee ficheros: todo se pide al backend por HTTP." },
  { name: "node:fs", message: "La interfaz no lee ficheros: todo se pide al backend por HTTP." },
  { name: "path", message: "La interfaz no lee ficheros: todo se pide al backend por HTTP." },
  { name: "node:path", message: "La interfaz no lee ficheros: todo se pide al backend por HTTP." },
];
const SIN_BACKEND = { group: ["**/backend/**", "**/backend"], message: "Nada de src/ importa del backend." };

const SOLO_EL_CLIENTE_HABLA = "Solo src/compartido/api/ habla con el servidor.";

export default defineConfig([
  globalIgnores(["dist", "src/compartido/api/esquema.d.ts"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, tseslint.configs.recommended, reactHooks.configs.flat.recommended],
    languageOptions: { globals: globals.browser },
  },
  {
    files: ["scripts/**/*.mjs", "*.config.{js,ts}"],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", { paths: SIN_DISCO, patterns: [SIN_BACKEND] }],
    },
  },
  // Las pantallas no llaman al servidor: pasan por el cliente de compartido/api.
  ...FUNCIONALIDADES.map((propia) => ({
    files: [`src/features/${propia}/**/*.{ts,tsx}`],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: SOLO_EL_CLIENTE_HABLA },
        { name: "EventSource", message: SOLO_EL_CLIENTE_HABLA },
        { name: "XMLHttpRequest", message: SOLO_EL_CLIENTE_HABLA },
        { name: "WebSocket", message: SOLO_EL_CLIENTE_HABLA },
      ],
      "no-restricted-imports": [
        "error",
        {
          paths: [...SIN_DISCO, { name: "openapi-fetch", message: SOLO_EL_CLIENTE_HABLA }],
          patterns: [
            SIN_BACKEND,
            // Las funcionalidades no se importan entre sí (RNF-02).
            ...FUNCIONALIDADES.filter((otra) => otra !== propia).map((otra) => ({
              group: [`**/features/${otra}/**`, `../${otra}/**`, `../${otra}`],
              message: `features/${propia} no importa de features/${otra}: lo común sube a compartido/.`,
            })),
          ],
        },
      ],
    },
  })),
]);
