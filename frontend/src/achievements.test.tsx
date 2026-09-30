// Мотивация 2.0 (2/4): сетка достижений по категориям, прогресс до следующего уровня, скрытые — «?».
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  today: "2026-09-13",
  locale: "ru",
};

function category(name: string, value: number, targets: number[], earned: number) {
  return {
    category: name,
    value,
    next_target: earned >= targets.length ? null : targets[earned],
    levels: targets.map((target, i) => ({
      code: `${name}_${i + 1}`,
      level: i + 1,
      target,
      earned_on: i < earned ? "2026-09-10" : null,
    })),
  };
}

const PROGRESS = {
  xp: 120,
  level: 3,
  level_start_xp: 120,
  next_level_xp: 210,
  streak: 2,
  best_streak: 9,
  freezes: 2,
  days_30: 17,
  days_total: 41,
  weekly_goal: 3,
  week_days: 1,
  weekend_days: [] as number[],
  recovery: null,
  achievements: [
    {
      code: "first_entry",
      title: "Первая запись",
      description: "Описание",
      earned_on: "2026-09-01",
    },
    { code: "consistency_1", title: "", description: "", earned_on: "2026-09-10" },
  ],
  categories: [
    category("consistency", 12, [7, 30, 100], 1),
    category("depth", 0, [5, 25, 100], 0),
    category("explorer", 8, [2, 4, 8], 3),
    category("care", 5, [5, 25, 100], 1),
  ],
  hidden: [
    { code: "comeback", earned_on: "2026-09-11" },
    { code: "first_gratitude", earned_on: null },
    { code: "year_diary", earned_on: null },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function open() {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>((input) =>
      Promise.resolve(
        String(input) === "/api/me"
          ? reply(200, ME)
          : String(input) === "/api/progress"
            ? reply(200, PROGRESS)
            : reply(404, {}),
      ),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/profile"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("сетка по категориям: уровни, прогресс до следующего, завершённая категория", async () => {
  open();
  const grid = await screen.findByTestId("achievement-grid");
  expect(
    within(grid)
      .getAllByRole("heading", { level: 4 })
      .map((h) => h.textContent),
  ).toEqual(["Постоянство", "Глубина", "Исследователь", "Забота о себе"]);
  expect(screen.getByTestId("category-consistency-progress").textContent).toBe(
    "12 из 30 до следующего уровня",
  );
  expect(screen.getByTestId("category-depth-progress").textContent).toBe(
    "0 из 5 до следующего уровня",
  );
  expect(screen.getByTestId("category-explorer-progress").textContent).toBe("Все уровни получены");
  expect(screen.getByTestId("consistency_1").dataset.earned).toBe("yes");
  expect(screen.getByTestId("consistency_2").dataset.earned).toBe("no");
  expect(screen.getByTestId("consistency_2").textContent).toContain("Серебро");
  expect(screen.getByTestId("consistency_2").textContent).toContain("Пока не получено");
});

test("скрытые достижения — «?» до получения, после — название и дата", async () => {
  open();
  const hidden = await screen.findByTestId("hidden-achievements");
  expect(within(hidden).getByTestId("hidden-comeback").textContent).toContain(
    "Вернулся после паузы",
  );
  expect(within(hidden).getByTestId("hidden-first_gratitude").textContent).toBe("?");
  expect(hidden.textContent).not.toContain("Первая благодарность");
  expect(hidden.textContent).not.toContain("Год с дневником");
});

test("прежние достижения остаются списком «Первые шаги», новые в список не дублируются", async () => {
  open();
  await screen.findByText("Первая запись");
  const list = screen.getByTestId("achievements");
  expect(within(list).queryAllByRole("listitem")).toHaveLength(1);
  expect(screen.getByText("Первые шаги")).toBeTruthy();
});

test("отметки рефлексии в итоге дня отправляются с сохранением", async () => {
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      if (url === "/api/me") return Promise.resolve(reply(200, ME));
      if (url.startsWith("/api/day-reviews/") && init?.method === "PUT") {
        bodies.push(JSON.parse(String(init.body)));
        return Promise.resolve(
          reply(200, { id: 1, date: "2026-09-13", wellbeing: 5, mood: 5, reflection: "" }),
        );
      }
      if (url === "/api/progress") return Promise.resolve(reply(200, PROGRESS));
      return Promise.resolve(reply(200, []));
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/day"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByLabelText("Сделал маленький шаг"));
  fireEvent.click(screen.getByLabelText("Появился инсайт"));
  fireEvent.click(screen.getByTestId("save-review"));
  await waitFor(() => expect(bodies).toHaveLength(1));
  expect((bodies[0] as { marks: string[] }).marks).toEqual(["step", "insight"]);
});
