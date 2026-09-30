// Преемственность разборов: «Что изменилось», период по умолчанию, дубль, «Что ИИ помнит обо мне».
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

const JSON_HEADERS = { "Content-Type": "application/json" };

function reply(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  });
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
const NO_MOOD = { points: [], average_mood: null, average_wellbeing: null, trend: "unknown" };
const ACTIVE = {
  start: "2026-09-23",
  end: "2026-09-29",
  active: true,
  truncated: false,
  last_analysis_id: null,
};

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
    "GET /api/analyses/period": () => reply(200, ACTIVE),
    "GET /api/analyses/memory": () => reply(200, { digest: "", updated_at: null }),
    "GET /api/analyses": () => reply(200, []),
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

test("блок «Что изменилось» виден, когда у разбора есть changes", async () => {
  const withChanges = analysis(2, { changes: ["Звонков стало меньше избегать", "Сон наладился"] });
  stubApi({ ...baseRoutes(), "GET /api/analyses": () => reply(200, [withChanges]) });
  openAnalysisPage();

  const block = await screen.findByTestId("analysis-changes");
  expect(block.textContent).toContain("Что изменилось с прошлого разбора");
  expect(block.textContent).toContain("Сон наладился");
});

test("без changes блока «Что изменилось» нет", async () => {
  stubApi({ ...baseRoutes(), "GET /api/analyses": () => reply(200, [analysis(1)]) });
  openAnalysisPage();

  await screen.findByTestId("analysis-result");
  expect(screen.queryByTestId("analysis-changes")).toBeNull();
});

test("период по умолчанию подставлен в поля из ответа сервера", async () => {
  stubApi(baseRoutes());
  openAnalysisPage();

  const start = (await screen.findByLabelText("С даты")) as HTMLInputElement;
  await waitFor(() => expect(start.value).toBe("2026-09-23"));
  expect((screen.getByLabelText("По дату") as HTMLInputElement).value).toBe("2026-09-29");
});

test("если новых записей нет, разбор неактивен и есть ссылка на последний", async () => {
  const last = analysis(3, { summary: "Прошлый разбор" });
  // более точные маршруты — раньше общего «GET /api/analyses» (выбор по началу ключа)
  const fetchMock = stubApi({
    "GET /api/analyses/3": () => reply(200, last),
    ...baseRoutes(),
    "GET /api/analyses/period": () =>
      reply(200, { ...ACTIVE, active: false, last_analysis_id: 3, start: "2026-09-29" }),
  });
  openAnalysisPage();
  fireEvent.click(await screen.findByLabelText(/Согласен/));

  const note = await screen.findByTestId("analysis-no-new");
  expect(note.textContent).toContain("новых записей");
  expect((screen.getByTestId("run-analysis") as HTMLButtonElement).disabled).toBe(true);

  fireEvent.click(screen.getByRole("button", { name: "Открыть последний разбор" }));
  expect((await screen.findByTestId("analysis-result")).textContent).toContain("Прошлый разбор");
  expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain("/api/analyses/3");
});

test("при усечении периода до 31 дня объясняется, как разобрать более ранние дни", async () => {
  stubApi({
    ...baseRoutes(),
    "GET /api/analyses/period": () => reply(200, { ...ACTIVE, truncated: true }),
  });
  openAnalysisPage();

  const note = await screen.findByText(/выбрав период вручную/);
  expect(note.textContent).toContain("31");
});

test("повтор того же разбора предлагает открыть существующий", async () => {
  const existing = analysis(5, { summary: "Уже есть такой разбор" });
  stubApi({
    "GET /api/analyses/5": () => reply(200, existing),
    ...baseRoutes(),
    "POST /api/analyses": () =>
      reply(409, { detail: { code: "analysis.duplicate", params: { existing_id: 5 } } }),
  });
  openAnalysisPage();
  fireEvent.click(await screen.findByLabelText(/Согласен/));
  fireEvent.click(screen.getByTestId("run-analysis"));

  expect((await screen.findByRole("alert")).textContent).toContain("уже есть");
  fireEvent.click(screen.getByRole("button", { name: "Открыть существующий разбор" }));
  expect((await screen.findByTestId("analysis-result")).textContent).toContain(
    "Уже есть такой разбор",
  );
});

test("«Что ИИ помнит обо мне» показывает дайджест и очищается кнопкой", async () => {
  let digest = "Избегает звонков; пробует по одному в день.";
  const fetchMock = stubApi({
    ...baseRoutes(),
    "GET /api/analyses/memory": () => reply(200, { digest, updated_at: "2026-09-29T10:00:00Z" }),
    "DELETE /api/analyses/memory": () => {
      digest = "";
      return reply(204, null);
    },
  });
  openAnalysisPage();

  expect((await screen.findByTestId("ai-memory-digest")).textContent).toContain("Избегает звонков");
  fireEvent.click(screen.getByRole("button", { name: "Очистить память" }));

  await waitFor(() => expect(screen.queryByTestId("ai-memory-digest")).toBeNull());
  expect(screen.getByTestId("ai-memory").textContent).toContain("Память очищена");
  const cleared = fetchMock.mock.calls.some(
    ([url, init]) => String(url) === "/api/analyses/memory" && init?.method === "DELETE",
  );
  expect(cleared).toBe(true);
});
