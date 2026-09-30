/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Сборка → frontend/dist, её отдаёт FastAPI (один порт для приложения, e2e и UI-замечаний).
// `pnpm dev` — горячая перезагрузка на :5173, запросы /api уходят на бэкенд.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    environment: "happy-dom",
    setupFiles: ["src/vitest.setup.ts"],
    // покрытие фронтенда: абсолютный минимум здесь, рост фиксирует храповик (.quality-baseline.json)
    coverage: {
      provider: "v8",
      include: ["src/**"],
      exclude: ["src/api.gen.ts", "src/main.tsx", "src/vitest.setup.ts", "src/**/*.test.*"],
      reporter: ["text-summary", "json-summary"],
      thresholds: { lines: 70, branches: 60 },
    },
  },
});
