// Мотивация 2.0 (4/4): квест дня — выбор 1 из 3, отметка, квест недели; при кризисе блока нет.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { DailyQuest } from "./components/DailyQuest";
import { ru } from "./i18n/ru";

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

function stub(routes: Record<string, (init?: RequestInit) => Response>) {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input).split("?")[0]}`;
    const handler = routes[key];
    return Promise.resolve(handler ? handler(init) : reply(404, { detail: "нет маршрута" }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function show(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

function daily(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    options: ["water", "stretch", "breathe"],
    picked: null,
    done: false,
    weekly: "strengths",
    ...over,
  };
}

test("три варианта на выбор, клик фиксирует выбор", async () => {
  const fetchMock = stub({
    "GET /api/daily-quest": () => reply(200, daily()),
    "POST /api/daily-quest/choose": (init) => {
      JSON.parse(String(init?.body));
      return reply(200, daily({ picked: "stretch", done: false }));
    },
    "GET /api/quests/library": () => reply(200, []),
  });
  show(<DailyQuest />);
  fireEvent.click(await screen.findByTestId("daily-option-stretch"));
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/daily-quest/choose")).toBe(
      true,
    ),
  );
  expect(await screen.findByTestId("daily-picked")).toBeTruthy();
  expect(screen.getByTestId("daily-picked").textContent).toContain(ru["daily.option.stretch"]);
});

test("выполнение отмечается кнопкой, повтор — уже «готово»", async () => {
  stub({
    "GET /api/daily-quest": () => reply(200, daily({ picked: "water" })),
    "POST /api/daily-quest/done": () => reply(200, daily({ picked: "water", done: true })),
    "GET /api/quests/library": () => reply(200, []),
  });
  show(<DailyQuest />);
  fireEvent.click(await screen.findByRole("button", { name: ru["daily.mark"] }));
  expect(await screen.findByTestId("daily-done")).toBeTruthy();
});

test("квест недели от наставника с кнопкой принятия", async () => {
  const fetchMock = stub({
    "GET /api/daily-quest": () => reply(200, daily()),
    "GET /api/quests/library": () =>
      reply(200, [
        {
          code: "strengths",
          title: "Мои сильные стороны",
          description: "",
          direction: "positive",
          kind: "quest",
          steps: [],
        },
      ]),
    "POST /api/quests": () =>
      reply(201, { id: 1, source: "library", template_code: "strengths", kind: "quest" }),
  });
  show(<DailyQuest />);
  await screen.findByTestId("daily-weekly");
  await waitFor(() =>
    expect(screen.getByTestId("daily-weekly").textContent).toContain("Мои сильные стороны"),
  );
  fireEvent.click(screen.getByRole("button", { name: ru["daily.weekly.take"] }));
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/quests")).toBe(true),
  );
});

test("кризис: блока квеста дня нет", () => {
  stub({ "GET /api/daily-quest": () => reply(200, daily()) });
  const { container } = show(<DailyQuest crisis />);
  expect(container.querySelector('[data-testid="daily-quest"]')).toBeNull();
});
