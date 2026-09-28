/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Сборка → frontend/dist, её отдаёт FastAPI (один порт для приложения, e2e и UI-замечаний).
// `pnpm dev` — горячая перезагрузка на :5173, запросы /api уходят на бэкенд.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "happy-dom" },
});
