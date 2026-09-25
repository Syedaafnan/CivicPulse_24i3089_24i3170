import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev server only: proxy /api to a backend you run yourself (`npm run dev`).
// In containers nginx does this proxying, so no backend URL is ever baked into the bundle.
const devTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": devTarget } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
