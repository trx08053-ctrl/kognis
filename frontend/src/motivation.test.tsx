// Мотивация 2.0: экран прогресса при обрыве серии (нет «0», есть дни за 30 и восстановление), цель, выходные.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

const JSON_HEADERS = { "Content-Type": "application/json" };

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

const ME = {
  id: 1,
  email: "ann@example.com",
  advanced: false,
  timezone: "Europe/Moscow",
  today: "2026-09-13",
  locale: "ru",
};
const PROGRESS = {
  xp: 120,
  level: 3,
  level_start_xp: 120,
  next_level_xp: 210,
  streak: 0,
  best_streak: 9,
  freezes: 0,
  days_30: 17,
  days_total: 41,
  weekly_goal: 3,
  week_days: 1,
  weekend_days: [] as number[],
  recovery: { streak_before: 9, broken_on: "2026-09-12", expires_on: "2026-09-15" },
  achievements: [],
  categories: [],
  hidden: [],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type Handler = (url: string, init?: RequestInit) => Response;

function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const match = Object.keys(routes).find((route) => key.startsWith(route));
    const handler = match ? routes[match] : undefined;
    return Promise.resolve(
      handler ? handler(String(input), init) : reply(404, { detail: `нет ${key}` }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function openProfile() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/profile"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("при оборванной серии нет «0»: дни за 30, всего дней и предложение вернуть серию", async () => {
  stubApi({ "GET /api/me": () => reply(200, ME), "GET /api/progress": () => reply(200, PROGRESS) });
  openProfile();

  const panel = await screen.findByTestId("motivation");
  expect(within(panel).getByTestId("days-30").textContent).toBe(
    "Дней с дневником за последние 30: 17",
  );
  expect(within(panel).getByTestId("days-total").textContent).toBe("Всего дней с дневником: 41");
  expect(within(panel).queryByTestId("streak-line")).toBeNull();
  expect(panel.textContent).not.toMatch(/Серия: 0/);
  expect(within(panel).getByTestId("recovery").textContent).toContain(
    "Серия из 9 дн. прервалась — её можно вернуть",
  );
  // в шапке вместо «Серия: 0 дн.» — дни за 30
  expect(screen.queryByTestId("streak")).toBeNull();
  expect(screen.getByTestId("days-30-badge").textContent).toBe("За 30 дней: 17");
  expect(screen.queryByText(/Серия: 0/)).toBeNull();
});

test("заметка «что помешало» отправляется и возвращает серию", async () => {
  let body: unknown = null;
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "POST /api/progress/recovery": (_url, init) => {
      body = JSON.parse(String(init?.body));
      return reply(200, { ...PROGRESS, streak: 9, recovery: null });
    },
    "GET /api/progress": () => reply(200, PROGRESS),
  });
  openProfile();

  const button = await screen.findByRole("button", { name: "Вернуть серию" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Что помешало?"), { target: { value: "Болел" } });
  fireEvent.click(button);

  await waitFor(() =>
    expect(screen.getByTestId("streak-line").textContent).toBe("Серия: 9 дн. подряд"),
  );
  expect(body).toEqual({ note: "Болел" });
  expect(screen.queryByTestId("recovery")).toBeNull();
});

test("цель недели и выходные дни сохраняются, лишний выходной выбрать нельзя", async () => {
  const saved: unknown[] = [];
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "PUT /api/progress/settings": (_url, init) => {
      const payload = JSON.parse(String(init?.body)) as {
        weekend_days: number[];
        weekly_goal: number;
      };
      saved.push(payload);
      return reply(200, { ...PROGRESS, recovery: null, ...payload });
    },
    "GET /api/progress": () =>
      reply(200, { ...PROGRESS, recovery: null, weekend_days: [5, 6], week_days: 3 }),
  });
  openProfile();

  const goal = (await screen.findByTestId("weekly-goal")) as HTMLSelectElement;
  expect(screen.getByTestId("goal-done").textContent).toBe("Цель недели выполнена");
  expect((screen.getByTestId("weekend-0") as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByTestId("weekend-6") as HTMLInputElement).checked).toBe(true);

  fireEvent.change(goal, { target: { value: "5" } });
  await waitFor(() => expect(saved).toEqual([{ weekend_days: [5, 6], weekly_goal: 5 }]));
  fireEvent.click(screen.getByTestId("weekend-6"));
  await waitFor(() => expect(saved[1]).toEqual({ weekend_days: [5], weekly_goal: 5 }));
});
