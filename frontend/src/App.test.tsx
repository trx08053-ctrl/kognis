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

const emptyProgress = {
  xp: 0,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 0,
  achievements: [],
};

// ответы по адресу и методу: запросы идут параллельно, порядок между адресами не гарантирован
function stubApi(routes: Record<string, (init?: RequestInit) => Response>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const handler = routes[key];
    return Promise.resolve(handler ? handler(init) : reply(404, { detail: `нет маршрута ${key}` }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("аноним видит форму входа и после входа — дневник с записями", async () => {
  let loggedIn = false;
  const fetchMock = stubApi({
    "GET /api/me": () => (loggedIn ? reply(200, ME) : reply(401, { detail: "нужен вход" })),
    "POST /api/auth/login": () => {
      loggedIn = true;
      return reply(200, ME);
    },
    "GET /api/entries": () =>
      reply(200, [
        {
          id: 7,
          date: "2026-09-01",
          text: "Тревожный день",
          tags: ["работа"],
          emotions: [],
          protection: "plain",
          crisis: false,
          help: null,
        },
      ]),
    "GET /api/progress": () => reply(200, emptyProgress),
  });
  renderApp();

  fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "ann@example.com" } });
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "correct horse" } });
  fireEvent.click(screen.getByTestId("auth-submit"));

  expect(await screen.findByText("Тревожный день")).toBeTruthy();
  expect(screen.getByTestId("whoami").textContent).toBe("ann@example.com");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/login",
    expect.objectContaining({ method: "POST" }),
  );
});

test("показывает ошибку входа", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(reply(401, { detail: "нужен вход" }))
      .mockResolvedValueOnce(reply(401, { detail: "неверный email или пароль" })),
  );
  renderApp();
  fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "ann@example.com" } });
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "wrong wrong" } });
  fireEvent.click(screen.getByTestId("auth-submit"));
  expect((await screen.findByRole("alert")).textContent).toContain("неверный");
});

test("запись с кризисным сигналом показывает блок помощи с контактами", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, emptyProgress),
    "POST /api/entries": () =>
      reply(201, {
        id: 2,
        date: "2026-09-29",
        text: "хочу умереть",
        tags: [],
        emotions: [],
        protection: "plain",
        crisis: true,
        help: {
          message: "Вы не одни",
          contacts: [{ name: "Экстренные службы", phone: "112", note: "круглосуточно" }],
        },
      }),
  });
  renderApp();
  fireEvent.change(await screen.findByLabelText("Что произошло и что вы чувствуете"), {
    target: { value: "хочу умереть" },
  });
  fireEvent.click(screen.getByTestId("save-entry"));
  const block = await screen.findByTestId("help-block");
  expect(block.getAttribute("role")).toBe("alert");
  expect(block.textContent).toContain("Вы не одни");
  expect(screen.getByRole("link", { name: "112" }).getAttribute("href")).toBe("tel:112");
  expect(screen.getByTestId("disclaimer").textContent).toContain("не медицинская помощь");
});

test("запись под замком: заглушка, ошибка неверного пароля, затем текст", async () => {
  const opens: string[] = [];
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () =>
      reply(200, [
        {
          id: 5,
          date: "2026-09-29",
          text: "",
          tags: [],
          emotions: [],
          protection: "locked",
          crisis: false,
          help: null,
        },
      ]),
    "POST /api/entries/5/open": () => {
      // первая попытка — с неверным паролем, вторая — с верным
      opens.push("open");
      return opens.length > 1
        ? reply(200, {
            id: 5,
            date: "2026-09-29",
            text: "Тайная мысль",
            tags: [],
            emotions: [],
            protection: "locked",
            crisis: false,
            help: null,
          })
        : reply(403, { detail: "неверный пароль замка" });
    },
  });
  renderApp();

  expect((await screen.findByTestId("locked-stub")).textContent).toContain("закрыта замком");
  expect(screen.queryByText("Тайная мысль")).toBeNull();
  fireEvent.change(screen.getByLabelText("Пароль замка"), { target: { value: "неверный-пароль" } });
  fireEvent.click(screen.getByRole("button", { name: "Открыть" }));
  expect((await screen.findByRole("alert")).textContent).toContain("неверный пароль замка");
  expect(screen.queryByText("Тайная мысль")).toBeNull();

  fireEvent.change(screen.getByLabelText("Пароль замка"), {
    target: { value: "правильный-пароль" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Открыть" }));
  expect((await screen.findByTestId("opened-text")).textContent).toBe("Тайная мысль");
  expect(opens).toHaveLength(2);
});

test("приватная запись: предупреждение, на сервер уходит только шифртекст, открывается паролем", async () => {
  const stored: Record<string, unknown>[] = [];
  const bodies: string[] = [];
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/entries": () => reply(200, stored),
    // «сервер» сохраняет присланное как есть — так же, как настоящий, ничего не расшифровывая
    "POST /api/entries": (init) => {
      const sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
      bodies.push(String(init?.body));
      stored.push({
        id: 9,
        date: "2026-09-29",
        text: "",
        tags: [],
        emotions: [],
        protection: "private",
        crisis: false,
        cipher: sent.cipher,
        help: null,
      });
      return reply(201, stored[0]);
    },
  });
  renderApp();

  fireEvent.change(await screen.findByLabelText("Что произошло и что вы чувствуете"), {
    target: { value: "Тайная мысль" },
  });
  fireEvent.click(screen.getByLabelText(/Приватная запись/));
  expect(screen.getByTestId("private-warning").textContent).toContain("восстановить его нельзя");
  fireEvent.change(screen.getByLabelText(/Пароль записи/), {
    target: { value: "правильный-пароль" },
  });
  fireEvent.change(screen.getByLabelText("Повторите пароль"), {
    target: { value: "правильный-пароль" },
  });
  fireEvent.click(screen.getByTestId("save-entry"));

  await vi.waitFor(() => expect(screen.queryByTestId("private-stub")).toBeTruthy());
  const sent = JSON.parse(bodies[0] ?? "{}") as Record<string, unknown>;
  expect(sent.protection).toBe("private");
  expect(sent.text).toBe("");
  expect(bodies[0]).not.toContain("Тайная");
  expect(bodies[0]).not.toContain("правильный-пароль");

  fireEvent.change(screen.getByLabelText("Пароль записи"), {
    target: { value: "неверный-пароль" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Расшифровать" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Неверный пароль");
  fireEvent.change(screen.getByLabelText("Пароль записи"), {
    target: { value: "правильный-пароль" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Расшифровать" }));
  expect((await screen.findByTestId("private-text")).textContent).toBe("Тайная мысль");
});

test("виджет показывает уровень, серию и опыт", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () =>
      reply(200, {
        xp: 60,
        level: 2,
        level_start_xp: 50,
        next_level_xp: 120,
        streak: 3,
        achievements: [],
      }),
  });
  renderApp();
  expect((await screen.findByTestId("level")).textContent).toBe("Уровень 2");
  expect(screen.getByTestId("streak").textContent).toBe("Серия: 3 дн.");
  expect(screen.getByTestId("xp").textContent).toBe("Опыт: 60 из 120");
});

test("страница достижений показывает дату получения", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () =>
      reply(200, {
        ...emptyProgress,
        achievements: [
          {
            code: "first_entry",
            title: "Первая запись",
            description: "Сделана первая запись в дневнике",
            earned_on: "2026-09-01",
          },
        ],
      }),
  });
  renderApp();
  fireEvent.click(await screen.findByRole("link", { name: "Достижения" }));
  const list = await screen.findByTestId("achievements");
  expect(list.textContent).toContain("Первая запись");
  expect(list.textContent).toContain("Получено: 2026-09-01");
});

test("итог дня с кризисным сигналом в рефлексии показывает блок помощи", async () => {
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/day-reviews": () => reply(200, []),
    "PUT /api/day-reviews/2026-09-29": () =>
      reply(200, {
        id: 1,
        date: "2026-09-29",
        wellbeing: 3,
        mood: 3,
        reflection: "хочу умереть",
        help: {
          message: "Вы не одни",
          contacts: [{ name: "Экстренные службы", phone: "112", note: "круглосуточно" }],
        },
      }),
  });
  renderApp();
  fireEvent.click(await screen.findByRole("link", { name: "Итог дня" }));
  fireEvent.change(await screen.findByLabelText("Дата"), { target: { value: "2026-09-29" } });
  fireEvent.change(screen.getByLabelText("Рефлексия: что запомнилось сегодня"), {
    target: { value: "хочу умереть" },
  });
  fireEvent.click(screen.getByTestId("save-review"));
  const block = await screen.findByTestId("help-block");
  expect(block.textContent).toContain("Вы не одни");
});

test("разбор: без согласия кнопка выключена, с согласием показывает паттерны", async () => {
  const analysis = {
    id: 5,
    parent_id: null,
    direction: "cbt",
    start: "2026-09-23",
    end: "2026-09-29",
    status: "done",
    summary: "Неделя прошла напряжённо",
    patterns: [
      {
        title: "Избегание",
        description: "Откладываешь звонки",
        entry_ids: [1],
        quotes: ["страшно"],
      },
    ],
    questions: ["Что помогло бы начать?"],
    quest_ideas: [],
    answers: [],
    help: null,
  };
  const fetchMock = stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/analyses/directions": () => reply(200, [{ code: "cbt", title: "КПТ" }]),
    "POST /api/analyses": () => reply(201, analysis),
  });
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>((input, init) => {
      if (String(input).startsWith("/api/analyses/mood")) {
        return Promise.resolve(
          reply(200, { points: [], average_mood: null, average_wellbeing: null, trend: "unknown" }),
        );
      }
      return fetchMock(input, init);
    }),
  );
  renderApp();
  fireEvent.click(await screen.findByRole("link", { name: "Разбор" }));
  const run = await screen.findByTestId("run-analysis");
  expect((run as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/Согласен\(на\) передать записи/));
  expect((run as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(run);
  const result = await screen.findByTestId("analysis-result");
  expect(result.textContent).toContain("Избегание");
  expect(screen.getByLabelText("Что помогло бы начать?")).toBeTruthy();
});

test("экран квестов: принять из библиотеки и отметить шаг", async () => {
  const steps = [{ idx: 0, title: "Первый шаг", done_on: null }];
  const quest = {
    id: 5,
    source: "library",
    template_code: "catch_thought",
    kind: "quest",
    title: "Поймай мысль",
    description: "",
    created_on: "2026-09-01",
    completed_on: null,
    steps,
  };
  let taken = false;
  stubApi({
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/quests": () => reply(200, taken ? [quest] : []),
    "GET /api/quizzes": () => reply(200, []),
    "GET /api/quests/library": () =>
      reply(200, [
        {
          code: "catch_thought",
          title: "Поймай мысль",
          description: "Описание",
          direction: "cbt",
          kind: "quest",
          steps: ["Первый шаг"],
        },
      ]),
    "POST /api/quests": () => {
      taken = true;
      return reply(201, quest);
    },
  });
  renderApp();
  fireEvent.click(await screen.findByRole("link", { name: "Квесты" }));
  fireEvent.click(await screen.findByRole("button", { name: "Принять: Поймай мысль" }));
  const card = await screen.findByTestId("quest");
  expect(card.textContent).toContain("Выполнено шагов: 0 из 1");
});

test("пояс профиля меняется в интерфейсе и отправляется на сервер", async () => {
  let saved: unknown = null;
  stubApi({
    "GET /api/me": () => reply(200, saved ? { ...ME, timezone: "Asia/Vladivostok" } : ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/day-reviews": () => reply(200, []),
    "PUT /api/me/settings": (init) => {
      saved = JSON.parse(String(init?.body));
      return reply(200, { ...ME, timezone: "Asia/Vladivostok" });
    },
  });
  renderApp();
  const select = await screen.findByTestId("timezone-select");
  fireEvent.change(select, { target: { value: "Asia/Vladivostok" } });
  await waitFor(() => expect(saved).toEqual({ timezone: "Asia/Vladivostok" }));
  await waitFor(() =>
    expect((screen.getByTestId("timezone-select") as HTMLSelectElement).value).toBe(
      "Asia/Vladivostok",
    ),
  );
});

test("регистрация повторяется без пояса, если сервер не знает имя пояса браузера", async () => {
  vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
    timeZone: "Europe/Nowhere",
  } as Intl.ResolvedDateTimeFormatOptions);
  const bodies: unknown[] = [];
  let loggedIn = false;
  stubApi({
    "GET /api/me": () => (loggedIn ? reply(200, ME) : reply(401, { detail: "нужен вход" })),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, emptyProgress),
    "GET /api/day-reviews": () => reply(200, []),
    "POST /api/auth/register": (init) => {
      const body = JSON.parse(String(init?.body));
      bodies.push(body);
      if (body.timezone) return reply(422, { detail: "неизвестный часовой пояс" });
      loggedIn = true;
      return reply(201, ME);
    },
  });
  renderApp();
  fireEvent.click(await screen.findByRole("button", { name: "Нет аккаунта? Зарегистрироваться" }));
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ann@example.com" } });
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "correct horse" } });
  fireEvent.click(screen.getByTestId("auth-submit"));
  expect(await screen.findByTestId("whoami")).toBeTruthy();
  expect(bodies).toEqual([
    { email: "ann@example.com", password: "correct horse", timezone: "Europe/Nowhere" },
    { email: "ann@example.com", password: "correct horse", timezone: null },
  ]);
  vi.restoreAllMocks();
});
