import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        // In docker-compose this resolves via the compose network.
        // For local dev set VITE_API_TARGET=http://localhost:8000.
        target: process.env.VITE_API_TARGET || "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
