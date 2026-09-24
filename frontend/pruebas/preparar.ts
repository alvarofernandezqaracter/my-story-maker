import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { servidor } from "./servidor";

beforeAll(() => servidor.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  servidor.resetHandlers();
  if (typeof window !== "undefined") window.localStorage.clear();
});
afterAll(() => servidor.close());
