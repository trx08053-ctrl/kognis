// Постраничные списки: «Показать ещё», фильтры записей на сервере, варианты фильтров.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

const JSON_HEADERS = { "Content-Type": "application/json" };

function reply(status: number, body: unknown, next?: string): Response {
  const headers: Record<string, string> = next
    ? { ...JSON_HEADERS, "X-Next-Cursor": next }
    : JSON_HEADERS;
  return new Response(JSON.stringify(body), { status, headers });
}

const ME = {
  id: 1,
  email: "ann@example.com",
  advanced: true,
  timezone: "Europe/Moscow",
  today: "2026-09-29",
};
const PROGRESS = {
  xp: 10,
  level: 1,
  level_start_xp: 0,
  next_level_xp: 50,
  streak: 1,
  achievements: [],
};
const NO_MOOD = { points: [], average_mood: null, average_wellbeing: null, trend: "unknown" };
const NO_ENTRY = { crisis: false, cipher: null, help: null, protection: "plain" };

const ENTRIES = [
  {
    ...NO_ENTRY,
    id: 1,
    date: "2026-09-10",
    text: "первая",
    tags: ["работа"],
    emotions: ["тревога"],
  },
  { ...NO_ENTRY, id: 2, date: "2026-09-20", text: "вторая", tags: ["семья"], emotions: [] },
];

type Handler = (url: string) => Response;

// маршрут «МЕТОД /путь»; путь сравнивается по префиксу, поэтому «/labels» идёт раньше «/entries»
function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const url = String(input);
    const key = `${init?.method ?? "GET"} ${url}`;
    const match = Object.keys(routes).find((route) => key.startsWith(route));
    const handler = match ? routes[match] : undefined;
    return Promise.resolve(handler ? handler(url) : reply(404, { detail: `нет маршрута ${key}` }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function baseRoutes(): Record<string, Handler> {
  return {
    "GET /api/me": () => reply(200, ME),
    "GET /api/progress": () => reply(200, PROGRESS),
    "GET /api/day-reviews": () => reply(200, []),
    "GET /api/analyses/mood": () => reply(200, NO_MOOD),
  };
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

// «сервер» отбирает записи по параметрам запроса — фильтры считает не браузер
function filteringEntries(url: string): Response {
  const query = new URL(url, "http://localhost").searchParams;
  const tag = query.get("tag") ?? "";
  const from = query.get("from") ?? "";
  const to = query.get("to") ?? "";
  return reply(
    200,
    ENTRIES.filter(
      (entry) =>
        (!tag || entry.tags.includes(tag)) &&
        (!from || entry.date >= from) &&
        (!to || entry.date <= to),
    ),
  );
}

test("Advanced: фильтры уходят на сервер, варианты — все теги и эмоции пользователя", async () => {
  const fetchMock = stubApi({
    ...baseRoutes(),
    "GET /api/entries/labels": () =>
      reply(200, { tags: ["работа", "семья"], emotions: ["тревога"] }),
    "GET /api/entries": () => reply(200, ENTRIES),
  });
  renderAt("/");
  expect(await screen.findByText("первая")).toBeTruthy();
  expect(await screen.findByRole("option", { name: "#семья" })).toBeTruthy();

  const requested = () => fetchMock.mock.calls.map(([url]) => decodeURIComponent(String(url)));
  fireEvent.change(screen.getByLabelText("Тег"), { target: { value: "работа" } });
  await waitFor(() => expect(requested()).toContain("/api/entries?limit=30&tag=работа"));
  fireEvent.change(screen.getByLabelText("Тег"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("Эмоция"), { target: { value: "тревога" } });
  await waitFor(() => expect(requested()).toContain("/api/entries?limit=30&emotion=тревога"));
  fireEvent.change(screen.getByLabelText("Эмоция"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("С даты"), { target: { value: "2026-09-15" } });
  fireEvent.change(screen.getByLabelText("По дату"), { target: { value: "2026-09-16" } });
  await waitFor(() =>
    expect(requested()).toContain("/api/entries?limit=30&from=2026-09-15&to=2026-09-16"),
  );
});

test("Advanced: фильтр без результатов и возврат к полному списку", async () => {
  stubApi({
    ...baseRoutes(),
    "GET /api/entries/labels": () => reply(200, { tags: ["работа"], emotions: [] }),
    "GET /api/entries": filteringEntries,
  });
  renderAt("/");
  expect(await screen.findByText("вторая")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("С даты"), { target: { value: "2026-09-15" } });
  await waitFor(() => expect(screen.queryByText("первая")).toBeNull());
  fireEvent.change(screen.getByLabelText("По дату"), { target: { value: "2026-09-16" } });
  expect(await screen.findByText("По фильтрам ничего не найдено.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("С даты"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("По дату"), { target: { value: "" } });
  expect(await screen.findByText("первая")).toBeTruthy();
});

test("Advanced: первая страница, «Показать ещё» подгружает следующую по курсору", async () => {
  const entry = (id: number) => ({
    ...NO_ENTRY,
    id,
    date: "2026-09-01",
    text: `запись ${id}`,
    tags: [],
    emotions: [],
  });
  const fetchMock = stubApi({
    ...baseRoutes(),
    "GET /api/entries/labels": () => reply(200, { tags: [], emotions: [] }),
    "GET /api/entries": (url) =>
      url.includes("cursor=2026-09-01.2")
        ? reply(200, [entry(1)])
        : reply(200, [entry(3), entry(2)], "2026-09-01.2"),
  });
  renderAt("/");
  expect(await screen.findByText("запись 3")).toBeTruthy();
  expect(screen.queryByText("запись 1")).toBeNull();
  fireEvent.click(screen.getByTestId("more-entries"));
  expect(await screen.findByText("запись 1")).toBeTruthy();
  expect(screen.getByText("запись 3")).toBeTruthy();
  expect(screen.queryByTestId("more-entries")).toBeNull();
  expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
    "/api/entries?limit=30&cursor=2026-09-01.2",
  );
});

test("итоги дня: история подгружается по «Показать ещё»", async () => {
  const review = (id: number, date: string) => ({
    id,
    date,
    wellbeing: 5,
    mood: 5,
    reflection: `итог ${id}`,
  });
  stubApi({
    ...baseRoutes(),
    "GET /api/day-reviews": (url) =>
      url.includes("cursor=")
        ? reply(200, [review(1, "2026-09-01")])
        : reply(200, [review(2, "2026-09-02")], "2026-09-02"),
  });
  renderAt("/day");
  expect(await screen.findByText("итог 2")).toBeTruthy();
  fireEvent.click(screen.getByTestId("more-reviews"));
  expect(await screen.findByText("итог 1")).toBeTruthy();
  expect(screen.queryByTestId("more-reviews")).toBeNull();
});
