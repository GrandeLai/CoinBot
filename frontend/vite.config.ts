import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api/backtest": {
        target: "http://127.0.0.1:8002",
        changeOrigin: true,
      },
      "/api/walk-forward": {
        target: "http://127.0.0.1:8002",
        changeOrigin: true,
      },
      "/api/optimize": {
        target: "http://127.0.0.1:8002",
        changeOrigin: true,
      },
      "/api/indicators": {
        target: "http://127.0.0.1:8002",
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
});
