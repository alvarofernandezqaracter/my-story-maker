import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// El backend no tiene CORS: el navegador pide /api/... a Vite y Vite lo reenvía
// al servidor quitando el /api. Mismo origen, sin tocar el backend.
const proxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (ruta: string) => ruta.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
