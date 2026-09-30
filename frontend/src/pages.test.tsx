// Ветвления страниц: ошибки загрузки, пустые состояния, фильтры, повторные действия.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { greeting } from "./pages/HomePage";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// тело ошибки API: код и параметры вместо фразы
function err(code: string, params: Record<string, string | number> = {}) {
  return { detail: { code, params } };
}

const ME = {
  id: 1,
  email: "ann@example.com",
  advanced: false,
  timezone: "Europe/Moscow",
  today: "2026-09-29",
};
const ADVANCED = { ...ME, advanced: true };

const PROGRESS = {
  xp: 10,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 1,
  best_streak: 1,
  freezes: 2,
  days_30: 1,
  days_total: 1,
  weekly_goal: 3,
  week_days: 1,
  weekend_days: [],
  recovery: null,
  achievements: [],
};

const NO_MOOD = { points: [], average_mood: null, average_wellbeing: null, trend: "unknown" };

const NO_ENTRY = { crisis: false, cipher: null, help: null, protection: "plain" };

type Handler = (init?: RequestInit) => Response;

// маршрут «МЕТОД /путь»; путь сравнивается по префиксу (у запросов настроения даты в строке)
function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const match = Object.keys(routes).find((route) => key.startsWith(route));
    const handler = match ? routes[match] : undefined;
    return Promise.resolve(handler ? handler(init) : reply(404, { detail: `нет маршрута ${key}` }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("главная: ошибки загрузки графика и записей показываются, а не молчат", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ADVANCED),
    "GET /api/progress": () => reply(500, err("server.internal")),
    "GET /api/day-reviews": () => reply(500, err("diary.entry_not_found")),
    "GET /api/analyses/mood": () => reply(500, err("analysis.no_data")),
    "GET /api/entries": () => reply(500, err("auth.required")),
  });
  renderAt("/");
  expect(
    await screen.findByText(/Не удалось загрузить график: За период нет записей и итогов дня/),
  ).toBeTruthy();
  expect(await screen.findByText("Нужен вход")).toBeTruthy();
  expect(await screen.findByText("Запись не найдена")).toBeTruthy();
});

test("главная, Advanced: пустой график и пустой список записей", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ADVANCED),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/analyses/mood": () => reply(200, NO_MOOD),
    "GET /api/entries": () => reply(200, []),
  });
  renderAt("/");
  expect(await screen.findByText(/график появится после первого/)).toBeTruthy();
  expect(await screen.findByText("Пока нет записей.")).toBeTruthy();
  expect(screen.getByText("Сегодня итог ещё не подведён.")).toBeTruthy();
});

test("простой режим показывает только последние записи без фильтров", async () => {
  const many = Array.from({ length: 7 }, (_, i) => ({
    ...NO_ENTRY,
    id: i + 1,
    date: "2026-09-01",
    text: `запись ${i + 1}`,
    tags: [],
    emotions: [],
  }));
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () => reply(200, many),
  });
  renderAt("/");
  expect(await screen.findByText("запись 5")).toBeTruthy();
  expect(screen.queryByText("запись 6")).toBeNull();
  expect(screen.queryByTestId("entry-filters")).toBeNull();
});

test("форма записи: свои теги и эмоции через запятую, Enter и уход из поля", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () => reply(200, []),
  });
  renderAt("/");
  const tags = await screen.findByLabelText("Теги");
  fireEvent.change(tags, { target: { value: "дом, учёба," } });
  expect(screen.getByRole("button", { name: "Убрать тег: дом" })).toBeTruthy();
  fireEvent.change(tags, { target: { value: "сон" } });
  fireEvent.keyDown(tags, { key: "Enter" });
  expect(screen.getByRole("button", { name: "Убрать тег: сон" })).toBeTruthy();
  fireEvent.keyDown(tags, { key: "a" });
  fireEvent.change(tags, { target: { value: "спорт" } });
  fireEvent.blur(tags);
  expect(screen.getByRole("button", { name: "Убрать тег: спорт" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Убрать тег: дом" }));
  expect(screen.queryByRole("button", { name: "Убрать тег: дом" })).toBeNull();

  const emotion = screen.getByLabelText("Своя эмоция");
  fireEvent.change(emotion, { target: { value: "азарт," } });
  const chip = screen.getByRole("button", { name: "азарт" });
  expect(chip.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(chip);
  expect(screen.queryByRole("button", { name: "азарт" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "радость" }));
  expect(screen.getByRole("button", { name: "радость" }).getAttribute("aria-pressed")).toBe("true");
});

test("форма записи: приватная запись требует одинаковых паролей", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () => reply(200, []),
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Что произошло и что вы чувствуете"), {
    target: { value: "секрет" },
  });
  fireEvent.click(screen.getByLabelText("Приватная"));
  fireEvent.change(screen.getByLabelText(/Пароль записи/), { target: { value: "password-1" } });
  fireEvent.change(screen.getByLabelText("Повторите пароль"), { target: { value: "password-2" } });
  fireEvent.click(screen.getByTestId("save-entry"));
  expect((await screen.findByRole("alert")).textContent).toBe("Пароли не совпадают");
  fireEvent.click(screen.getByLabelText("Под замком"));
  expect(screen.getByLabelText(/Пароль замка/)).toBeTruthy();
});

test("итог дня: история, пустая история и ошибка сохранения", async () => {
  const fetchMock = stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "PUT /api/day-reviews/": () => reply(422, err("diary.mood_range", { min: 1, max: 10 })),
  });
  renderAt("/day");
  expect(await screen.findByText("Пока нет итогов дня.")).toBeTruthy();
  fireEvent.change(screen.getByRole("slider", { name: /Самочувствие/ }), {
    target: { value: "7" },
  });
  fireEvent.click(screen.getByTestId("save-review"));
  expect(await screen.findByText("Настроение: оценка от 1 до 10")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/day-reviews/"),
    expect.objectContaining({ method: "PUT" }),
  );
});

test("итог дня: сохранённый итог с кризисным блоком и история с рефлексией", async () => {
  const saved = {
    id: 3,
    date: "2026-09-29",
    wellbeing: 5,
    mood: 5,
    reflection: "устал",
    help: { message: "Вы не одни", contacts: [{ name: "Служба", phone: "112", note: "" }] },
  };
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, [saved]),
    "PUT /api/day-reviews/": () => reply(200, saved),
  });
  renderAt("/day");
  expect(await screen.findByTestId("reviews")).toBeTruthy();
  fireEvent.click(screen.getByTestId("save-review"));
  expect(await screen.findByText("Итог за 2026-09-29 сохранён.")).toBeTruthy();
  expect(await screen.findByTestId("help-block")).toBeTruthy();
});

const DIRECTIONS = [{ code: "cbt", title: "КПТ" }];
const DONE = {
  id: 1,
  parent_id: null,
  direction: "cbt",
  start: "2026-09-23",
  end: "2026-09-29",
  status: "done",
  summary: "Итог недели",
  patterns: [{ title: "Сон", description: "мало спите", entry_ids: [1, 2], quotes: ["не спал"] }],
  questions: ["Что помогло?"],
  quest_ideas: ["Прогулка"],
  changes: [],
  answers: [],
  help: null,
};

function analysisRoutes(extra: Record<string, Handler>): Record<string, Handler> {
  return {
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/analyses/directions": () => reply(200, DIRECTIONS),
    "GET /api/analyses/mood": () =>
      reply(200, {
        points: [{ date: "2026-09-28", mood: 6, wellbeing: 5 }],
        average_mood: 6,
        average_wellbeing: 5,
        trend: "up",
      }),
    ...extra,
  };
}

test("разбор: без согласия кнопка выключена; результат, идеи квестов и уточнение", async () => {
  stubApi(
    analysisRoutes({
      "POST /api/analyses/1/answers": () =>
        reply(200, { ...DONE, id: 2, parent_id: 1, questions: [], quest_ideas: [] }),
      "POST /api/analyses": () => reply(200, DONE),
      "POST /api/quests/from-analysis": () => reply(500, err("gameplay.idea_unknown")),
    }),
  );
  renderAt("/analysis");
  const run = await screen.findByTestId("run-analysis");
  expect((run as HTMLButtonElement).disabled).toBe(true);
  expect(await screen.findByText(/настроение растёт/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText(/Согласен/));
  fireEvent.click(run);
  expect(await screen.findByTestId("analysis-result")).toBeTruthy();
  expect(screen.getByText("Итог недели")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Принять квест: Прогулка" }));
  expect(await screen.findByText("Нет такой идеи")).toBeTruthy();

  fireEvent.change(screen.getByLabelText("Что помогло?"), { target: { value: "сон" } });
  fireEvent.click(screen.getByRole("button", { name: "Уточнить разбор" }));
  await waitFor(() => expect(screen.queryByLabelText("Что помогло?")).toBeNull());
});

test("разбор: принятая идея ведёт в квесты; кризис вместо паттернов; ошибка запуска", async () => {
  let call = 0;
  stubApi(
    analysisRoutes({
      "POST /api/analyses": () => {
        call += 1;
        if (call === 1) return reply(500, err("ai.http_server", { status: 500 }));
        if (call === 2) return reply(200, DONE);
        return reply(200, {
          ...DONE,
          status: "crisis",
          summary: null,
          patterns: [],
          questions: [],
          quest_ideas: [],
          changes: [],
          help: { message: "Вы не одни", contacts: [] },
        });
      },
      "POST /api/quests/from-analysis": () => reply(201, { id: 1 }),
    }),
  );
  renderAt("/analysis");
  fireEvent.click(await screen.findByLabelText(/Согласен/));
  const run = screen.getByTestId("run-analysis");
  fireEvent.click(run);
  expect(
    await screen.findByText("Провайдер ИИ вернул ошибку 500: сбой на стороне провайдера"),
  ).toBeTruthy();
  fireEvent.click(run);
  fireEvent.click(await screen.findByRole("button", { name: "Принять квест: Прогулка" }));
  expect(await screen.findByText(/Квест принят/)).toBeTruthy();
  fireEvent.click(run);
  expect(await screen.findByTestId("analysis-crisis")).toBeTruthy();
  expect(screen.getByTestId("help-block")).toBeTruthy();
});

test("разбор: пустая динамика настроения и ошибка её загрузки", async () => {
  stubApi(analysisRoutes({ "GET /api/analyses/mood": () => reply(200, NO_MOOD) }));
  renderAt("/analysis");
  expect(await screen.findByText("За период нет итогов дня.")).toBeTruthy();
  cleanup();
  stubApi(analysisRoutes({ "GET /api/analyses/mood": () => reply(500, err("analysis.no_data")) }));
  renderAt("/analysis");
  expect(await screen.findByText(/За период нет записей и итогов дня/)).toBeTruthy();
});

test("профиль: переключатель Advanced возвращается при ошибке сервера, часовой пояс сохраняется", async () => {
  const fetchMock = stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () =>
      reply(200, {
        ...PROGRESS,
        achievements: [
          {
            code: "first",
            title: "Первая запись",
            description: "Вы начали",
            earned_on: "2026-09-01",
          },
        ],
      }),
    "PUT /api/me/settings": (init) => {
      const body = JSON.parse(String(init?.body)) as { advanced?: boolean };
      return body.advanced === undefined
        ? reply(200, { ...ME, timezone: "UTC" })
        : reply(500, err("settings.empty"));
    },
  });
  renderAt("/profile");
  const toggle = (await screen.findByTestId("advanced-toggle")) as HTMLInputElement;
  expect(await screen.findByText("Первая запись")).toBeTruthy();
  fireEvent.click(toggle);
  expect(await screen.findByText("Нечего сохранять")).toBeTruthy();
  await waitFor(() => expect(toggle.checked).toBe(false));

  const zone = screen.getByTestId("timezone-select") as HTMLSelectElement;
  const other = Array.from(zone.options).find((option) => option.value !== ME.timezone);
  expect(other).toBeDefined();
  fireEvent.change(zone, { target: { value: other?.value } });
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/me/settings",
      expect.objectContaining({ body: JSON.stringify({ timezone: other?.value }) }),
    ),
  );
});

test("оболочка: смена темы и выход", async () => {
  const fetchMock = stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () => reply(200, []),
    "POST /api/auth/logout": () => new Response(null, { status: 204 }),
  });
  renderAt("/");
  const theme = await screen.findByTestId("theme-toggle");
  const before = theme.textContent;
  fireEvent.click(theme);
  expect(screen.getByTestId("theme-toggle").textContent).not.toBe(before);
  fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("не 401 при загрузке профиля: показывается ошибка, а не форма входа", async () => {
  stubApi({ "GET /api/me": () => reply(500, err("server.internal")) });
  renderAt("/");
  expect(await screen.findByText("Внутренняя ошибка")).toBeTruthy();
  expect(screen.queryByTestId("auth-submit")).toBeNull();
});

test("приветствие зависит от часа: утро, день, вечер, ночь", () => {
  expect([4, 5, 11, 12, 17, 18, 22, 23].map(greeting)).toEqual([
    "Доброй ночи",
    "Доброе утро",
    "Доброе утро",
    "Добрый день",
    "Добрый день",
    "Добрый вечер",
    "Добрый вечер",
    "Доброй ночи",
  ]);
});

test("лендинг для вошедшего на /welcome: нет форм входа, есть «Открыть дневник»", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
  });
  renderAt("/welcome");
  const open = await screen.findAllByRole("link", { name: "Открыть дневник" });
  expect(open.length).toBeGreaterThan(0);
  expect(screen.queryByTestId("auth-submit")).toBeNull();
  expect(screen.queryByLabelText("Пароль")).toBeNull();
  expect(screen.queryByTestId("cta-header")).toBeNull();
});
