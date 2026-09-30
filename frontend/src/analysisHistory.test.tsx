// История разборов: последний открыт сразу, «Показать ещё», открытие прошлого, удаление.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

const JSON_HEADERS = { "Content-Type": "application/json" };

function reply(status: number, body: unknown, next?: string): Response {
  const headers: Record<string, string> = next
    ? { ...JSON_HEADERS, "X-Next-Cursor": next }
    : JSON_HEADERS;
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers });
}

const ME = {
  id: 1,
  email: "ann@example.com",
  advanced: false,
  timezone: "Europe/Moscow",
  today: "2026-09-29",
  locale: "ru",
};
const PROGRESS = {
  xp: 0,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 0,
  achievements: [],
};
const PERIOD = {
  start: "2026-09-23",
  end: "2026-09-29",
  active: true,
  truncated: false,
  last_analysis_id: null,
};
const NO_MOOD = { points: [], average_mood: null, average_wellbeing: null, trend: "unknown" };

function analysis(id: number, extra: Record<string, unknown> = {}) {
  return {
    id,
    parent_id: null,
    direction: "cbt",
    start: "2026-09-01",
    end: "2026-09-07",
    status: "done",
    summary: `Итог разбора ${id}`,
    patterns: [],
    questions: [],
    quest_ideas: [],
    changes: [],
    answers: [],
    created_at: `2026-09-${10 + id}T09:00:00Z`,
    help: null,
    ...extra,
  };
}

const OLD = analysis(1, {
  summary: "Старая неделя",
  patterns: [
    {
      title: "Избегание",
      description: "Откладываешь звонки",
      entry_ids: [4],
      quotes: ["страшно звонить"],
    },
  ],
  questions: ["Что помогло бы начать?"],
  answers: ["Позвонить утром"],
});
const NEW = analysis(2, { summary: "Свежая неделя" });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type Handler = (url: string, init?: RequestInit) => Response;

function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const url = String(input);
    const key = `${init?.method ?? "GET"} ${url}`;
    const match = Object.keys(routes).find((route) => key.startsWith(route));
    const handler = match ? routes[match] : undefined;
    return Promise.resolve(handler ? handler(url, init) : reply(404, { detail: `нет ${key}` }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function baseRoutes(): Record<string, Handler> {
  return {
    "GET /api/me": () => reply(200, ME),
    "GET /api/entries": () => reply(200, []),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/analyses/directions": () => reply(200, [{ code: "cbt", title: "КПТ" }]),
    "GET /api/analyses/mood": () => reply(200, NO_MOOD),
    "GET /api/analyses/period": () => reply(200, PERIOD),
    "GET /api/analyses/memory": () => reply(200, { digest: "", updated_at: null }),
  };
}

function openAnalysisPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/analysis"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("последний разбор открыт по умолчанию, список — новые сверху с датой, периодом и статусом", async () => {
  stubApi({ ...baseRoutes(), "GET /api/analyses": () => reply(200, [NEW, OLD]) });
  openAnalysisPage();

  const result = await screen.findByTestId("analysis-result");
  expect(result.textContent).toContain("Свежая неделя");
  const rows = await screen.findAllByTestId("analysis-history-item");
  expect(rows).toHaveLength(2);
  expect(rows[0]?.textContent).toContain("КПТ");
  expect(rows[0]?.textContent).toContain("готов");
  expect(rows[0]?.textContent).toMatch(/2026/);
  expect(
    within(rows[0] as HTMLElement).getByRole("button", { name: /Открыть разбор/ }),
  ).toBeTruthy();
});

test("«Показать ещё» дозагружает следующую страницу по смещению из заголовка", async () => {
  const fetchMock = stubApi({
    ...baseRoutes(),
    "GET /api/analyses?offset=1": () => reply(200, [OLD]),
    "GET /api/analyses": () => reply(200, [NEW], "1"),
  });
  openAnalysisPage();

  expect(await screen.findAllByTestId("analysis-history-item")).toHaveLength(1);
  fireEvent.click(await screen.findByTestId("more-analyses"));
  await waitFor(() => expect(screen.getAllByTestId("analysis-history-item")).toHaveLength(2));
  expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain("/api/analyses?offset=1");
  expect(screen.queryByTestId("more-analyses")).toBeNull();
});

test("открытие прошлого разбора показывает паттерны, цитаты, вопросы и уточнение", async () => {
  stubApi({ ...baseRoutes(), "GET /api/analyses": () => reply(200, [NEW, OLD]) });
  openAnalysisPage();
  await screen.findByText("Свежая неделя");

  const rows = await screen.findAllByTestId("analysis-history-item");
  fireEvent.click(within(rows[1] as HTMLElement).getByRole("button", { name: /Открыть разбор/ }));

  const result = await screen.findByTestId("analysis-result");
  expect(result.textContent).toContain("Старая неделя");
  expect(result.textContent).toContain("Избегание");
  expect(result.textContent).toContain("страшно звонить");
  expect(result.textContent).toContain("Позвонить утром");
  expect(screen.getByLabelText("Что помогло бы начать?")).toBeTruthy();
});

test("удаление: подтверждение, DELETE, разбор пропадает, открывается предыдущий", async () => {
  let items = [NEW, OLD];
  const fetchMock = stubApi({
    ...baseRoutes(),
    "GET /api/analyses": () => reply(200, items),
    "DELETE /api/analyses/2": () => {
      items = [OLD];
      return reply(204, null);
    },
  });
  openAnalysisPage();
  await screen.findByText("Свежая неделя");

  const first = (await screen.findAllByTestId("analysis-history-item"))[0] as HTMLElement;
  fireEvent.click(within(first).getByRole("button", { name: /Удалить разбор/ }));
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  fireEvent.click(within(first).getByRole("button", { name: "Да, удалить" }));

  await waitFor(() => expect(screen.getAllByTestId("analysis-history-item")).toHaveLength(1));
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE");
  expect(call?.[1]?.headers).toMatchObject({ "Content-Type": "application/json" });
  await waitFor(() =>
    expect(screen.getByTestId("analysis-result").textContent).toContain("Старая неделя"),
  );
});

test("отмена удаления ничего не отправляет", async () => {
  const fetchMock = stubApi({ ...baseRoutes(), "GET /api/analyses": () => reply(200, [NEW]) });
  openAnalysisPage();
  const row = (await screen.findAllByTestId("analysis-history-item"))[0] as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: /Удалить разбор/ }));
  fireEvent.click(within(row).getByRole("button", { name: "Отмена" }));
  expect(within(row).getByRole("button", { name: /Удалить разбор/ })).toBeTruthy();
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
});

test("пустая история: понятная подсказка, разбора нет", async () => {
  stubApi({ ...baseRoutes(), "GET /api/analyses": () => reply(200, []) });
  openAnalysisPage();
  expect(await screen.findByText("Пока нет сохранённых разборов.")).toBeTruthy();
  expect(screen.queryByTestId("analysis-result")).toBeNull();
});

test("кризисный разбор из истории: без паттернов, статус «нужна поддержка»", async () => {
  stubApi({
    ...baseRoutes(),
    "GET /api/analyses": () =>
      reply(200, [
        analysis(3, { status: "crisis", summary: null, created_at: "2026-09-13T09:00:00Z" }),
      ]),
  });
  openAnalysisPage();
  expect(await screen.findByTestId("analysis-crisis")).toBeTruthy();
  expect((await screen.findByTestId("analysis-history-item")).textContent).toContain(
    "нужна поддержка",
  );
});
