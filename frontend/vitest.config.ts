import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "http://localhost:5173" } },
    setupFiles: ["./pruebas/preparar.ts"],
    include: ["pruebas/**/*.test.{ts,tsx}"],
  },
});
