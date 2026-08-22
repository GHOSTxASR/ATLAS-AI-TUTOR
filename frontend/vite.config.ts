/// <reference types="vitest" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const backendPort = env.LEARNINGOS_PORT || process.env.LEARNINGOS_PORT || "8000";
  const backendHttp = `http://127.0.0.1:${backendPort}`;
  const backendWs = `ws://127.0.0.1:${backendPort}`;

  return {
    plugins: [react(), tailwindcss()],
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": backendHttp,
        "/ws": {
          target: backendWs,
          ws: true,
        },
      },
    },
  };
});
