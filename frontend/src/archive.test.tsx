// Мотивация 2.0 (4/4): хранитель архива — «В этот день» и мозаика настроения за год.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { shiftDay } from "./dates";
import { ru } from "./i18n/ru";
import { ArchivePage } from "./pages/ArchivePage";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stub(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn<typeof fetch>((input) => {
    const key = `GET ${String(input).split("?")[0]}`;
    const handler = routes[key];
    return Promise.resolve(handler ? handler() : reply(404, { detail: "нет маршрута" }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ArchivePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("«В этот день»: записи год и месяц назад с пометкой давности", async () => {
  stub({
    "GET /api/archive/on-this-day": () =>
      reply(200, {
        entries: [
          {
            id: 1,
            date: "2025-10-01",
            ago: "year",
            text: "Год назад был тёплый день",
            tags: ["осень"],
            emotions: [],
          },
          {
            id: 2,
            date: "2026-09-01",
            ago: "month",
            text: "Месяц назад всё получилось",
            tags: [],
            emotions: [],
          },
        ],
      }),
    "GET /api/archive/mood-year": () => reply(200, { days: [] }),
  });
  show();
  const found = await screen.findByTestId("on-this-day");
  expect(await screen.findByText("Год назад был тёплый день")).toBeTruthy();
  expect(found.textContent).toContain(ru["archive.ago.year"]);
  expect(await screen.findByText("Месяц назад всё получилось")).toBeTruthy();
  expect(found.textContent).toContain(ru["archive.ago.month"]);
});

test("«В этот день»: пусто — мягкая подсказка вместо пустоты", async () => {
  stub({
    "GET /api/archive/on-this-day": () => reply(200, { entries: [] }),
    "GET /api/archive/mood-year": () => reply(200, { days: [] }),
  });
  show();
  expect(await screen.findByText(ru["archive.on_this_day.empty"])).toBeTruthy();
});

test("мозаика: клетка дня с итогом окрашена, счётчик дней сходится", async () => {
  const today = "2026-10-01"; // «сегодня» приходит с сервера — по поясу профиля, не из браузера
  stub({
    "GET /api/me": () =>
      reply(200, {
        id: 1,
        email: "a@example.com",
        advanced: false,
        timezone: "UTC",
        locale: "ru",
        today,
      }),
    "GET /api/archive/on-this-day": () => reply(200, { entries: [] }),
    "GET /api/archive/mood-year": () =>
      reply(200, {
        days: [
          { date: shiftDay(today, 0), mood: 9 },
          { date: shiftDay(today, -10), mood: 2 },
        ],
      }),
  });
  show();
  const mosaic = await screen.findByTestId("mood-mosaic");
  const cells = mosaic.querySelectorAll(".mood-cell");
  expect(cells.length).toBe(365);
  expect((await screen.findByTestId("mood-year-count")).textContent).toBe(
    ru["archive.mood_year.days"].replace("{count}", "2"),
  );
  await waitFor(() => {
    const painted = [...cells].filter(
      (c) => (c as HTMLElement).style.backgroundColor === "#22c55e",
    );
    expect(painted.length).toBe(1); // настроение 9 — зелёная клетка
  });
});

test("ошибка сервера: сообщение вместо падения страницы", async () => {
  stub({
    "GET /api/me": () =>
      reply(200, {
        id: 1,
        email: "a@example.com",
        advanced: false,
        timezone: "UTC",
        locale: "ru",
        today: "2026-10-01",
      }),
    "GET /api/archive/on-this-day": () =>
      reply(500, { detail: { code: "server.internal", params: {} } }),
    "GET /api/archive/mood-year": () =>
      reply(500, { detail: { code: "server.internal", params: {} } }),
  });
  show();
  await waitFor(() => expect(screen.getAllByText(ru["error.server.internal"])).toHaveLength(2));
});
