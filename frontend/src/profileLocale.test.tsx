// Язык интерфейса после входа берётся из профиля (/api/me), kognis-b7x.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { type Catalog, I18nProvider } from "./i18n";
import { ru } from "./i18n/ru";

const ME = {
  id: 1,
  email: "ann@example.com",
  advanced: false,
  timezone: "Europe/Moscow",
  today: "2026-09-29",
};
const PROGRESS = {
  xp: 0,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 0,
  achievements: [],
};
// тестовый второй язык живёт только здесь: в LOCALES его нет
const CATALOGS: Record<string, Catalog> = { ru, en: { ...ru, "shell.logout": "Log out" } };

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi(locale: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>((input) => {
      const url = String(input).split("?")[0];
      if (url === "/api/me") return Promise.resolve(json({ ...ME, locale }));
      if (url === "/api/progress") return Promise.resolve(json(PROGRESS));
      return Promise.resolve(json([]));
    }),
  );
}

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <I18nProvider catalogs={CATALOGS} initial="ru">
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  document.documentElement.lang = "ru";
});

test("язык профиля включается после входа", async () => {
  stubApi("en");
  renderApp();
  expect(await screen.findByText("Log out")).toBeTruthy();
  expect(document.documentElement.lang).toBe("en");
});

test("язык профиля без словаря игнорируется", async () => {
  stubApi("xx");
  renderApp();
  expect(await screen.findByText("Выйти")).toBeTruthy();
  expect(document.documentElement.lang).toBe("ru");
});
