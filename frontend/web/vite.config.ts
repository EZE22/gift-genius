import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The dev server forwards /api to the Gift Genius API (gift-genius-api on port 8001),
// so the browser talks to one origin and the API key never leaves the back end.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8001" },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
