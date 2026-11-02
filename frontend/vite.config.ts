/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

const API = "http://localhost:8000";

// Production: `vite build` writes frontend/dist with base "/" (FastAPI serves it; wired by the controller).
// Dev: the API paths are proxied to FastAPI on :8000 (uv run --env-file .env uvicorn sarthi.app.main:app --port 8000).
export default defineConfig({
  base: "/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      "/session": API,
      "/gallery": API,
      "/health": API,
      "/legacy": API,
    },
  },
  build: { outDir: "dist", sourcemap: false },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
});
