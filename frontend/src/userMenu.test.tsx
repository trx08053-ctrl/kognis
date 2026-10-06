// Меню аватара (kognis-2zb): раскрытие, закрытие по Escape и клику вне, тема и выход из меню.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const ME = {
  id: 1,
  email: "ann@example.com",
  advanced: false,
  timezone: "Europe/Moscow",
  today: "2026-09-29",
};

const PROGRESS = {
  xp: 10,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 0,
  best_streak: 0,
  freezes: 2,
  days_30: 3,
  days_total: 3,
  weekly_goal: 3,
  week_days: 0,
  weekend_days: [],
  recovery: null,
  achievements: [],
  categories: [],
  hidden: [],
};

type Handler = (init?: RequestInit) => Response;

function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const handler = routes[key] ?? routes[key.split("?")[0] ?? key];
    return Promise.resolve(handler ? handler(init) : reply(404, { detail: `нет маршрута ${key}` }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderApp() {
  const fetchMock = stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () => reply(200, []),
    "POST /api/auth/logout": () => new Response(null, { status: 204 }),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("меню раскрывается кнопкой-аватаром и закрывается Escape с возвратом фокуса", async () => {
  renderApp();
  const avatar = await screen.findByTestId("user-menu");
  expect(avatar.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(avatar);
  expect(avatar.getAttribute("aria-expanded")).toBe("true");
  // не-Escape меню не закрывает
  fireEvent.keyDown(document, { key: "a" });
  expect(avatar.getAttribute("aria-expanded")).toBe("true");
  fireEvent.keyDown(document, { key: "Escape" });
  expect(avatar.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(avatar);
  // повторный клик снова открывает
  fireEvent.click(avatar);
  expect(avatar.getAttribute("aria-expanded")).toBe("true");
});

test("клик вне закрывает меню, внутри — нет", async () => {
  renderApp();
  fireEvent.click(await screen.findByTestId("user-menu"));
  fireEvent.mouseDown(screen.getByTestId("whoami"));
  expect(screen.getByTestId("user-menu").getAttribute("aria-expanded")).toBe("true");
  fireEvent.mouseDown(document.body);
  expect(screen.getByTestId("user-menu").getAttribute("aria-expanded")).toBe("false");
});

test("в меню: email, тема переключается, выход отправляет logout", async () => {
  const fetchMock = renderApp();
  fireEvent.click(await screen.findByTestId("user-menu"));
  expect(screen.getByTestId("whoami").textContent).toBe("ann@example.com");
  const theme = screen.getByTestId("theme-toggle");
  const before = document.documentElement.classList.contains("dark");
  fireEvent.click(theme);
  expect(document.documentElement.classList.contains("dark")).toBe(!before);
  fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
