import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyProgress = {
  xp: 0,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 0,
  achievements: [],
};

// ответы по адресу и методу: запросы идут параллельно, порядок между адресами не гарантирован
function stubApi(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const handler = routes[key];
    return Promise.resolve(handler ? handler() : reply(404, { detail: `нет маршрута ${key}` }));
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
    "GET /api/me": () =>
      loggedIn
        ? reply(200, { id: 1, email: "ann@example.com" })
        : reply(401, { detail: "нужен вход" }),
    "POST /api/auth/login": () => {
      loggedIn = true;
      return reply(200, { id: 1, email: "ann@example.com" });
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
    "GET /api/me": () => reply(200, { id: 1, email: "ann@example.com" }),
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

test("виджет показывает уровень, серию и опыт", async () => {
  stubApi({
    "GET /api/me": () => reply(200, { id: 1, email: "ann@example.com" }),
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
    "GET /api/me": () => reply(200, { id: 1, email: "ann@example.com" }),
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
    "GET /api/me": () => reply(200, { id: 1, email: "ann@example.com" }),
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
