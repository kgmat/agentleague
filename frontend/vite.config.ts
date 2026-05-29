import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the backend at /api and /api/ws/*. In dev we proxy those
// to the backend so there's a single origin and no CORS friction; in Docker the
// same proxy target is overridden via VITE_API_TARGET.
const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api/ws": { target: API_TARGET, ws: true, changeOrigin: true },
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
});
