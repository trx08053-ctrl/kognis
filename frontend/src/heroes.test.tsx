// Мотивация 2.0 (3/4): цифровые герои — спутник, открытка, наставники; при кризисе героев нет.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import type { Companion } from "./api";
import { CompanionCard, MentorLine } from "./components/Heroes";
import { ru } from "./i18n/ru";
import { HomePage } from "./pages/HomePage";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const MENTORS = [
  { code: "analyst", direction: "cbt", unlocked: true },
  { code: "guide", direction: "act", unlocked: false },
  { code: "gardener", direction: "positive", unlocked: false },
  { code: "mechanic", direction: "activation", unlocked: true },
];

function companion(over: Partial<Companion> = {}): Companion {
  return {
    chosen: true,
    appearance: "fox",
    name: "Луна",
    address: "ty",
    stage: 2,
    days_total: 9,
    days_to_next: 12,
    resting: false,
    line: null,
    postcard: null,
    mentors: MENTORS,
    ...over,
  };
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

test("знакомство: облик, имя и обращение сохраняются, затем виден спутник", async () => {
  let saved: unknown = null;
  stub({
    "GET /api/companion": () =>
      reply(200, companion({ chosen: false, appearance: null, name: null, address: null })),
    "PUT /api/companion": (init) => {
      saved = JSON.parse(String(init?.body));
      return reply(200, companion({ appearance: "owl", stage: 1, days_total: 0, days_to_next: 7 }));
    },
  });
  show(<CompanionCard />);
  fireEvent.click(await screen.findByLabelText("Сова"));
  fireEvent.change(screen.getByLabelText("Имя"), { target: { value: "Луна" } });
  fireEvent.click(screen.getByLabelText("На «вы»"));
  fireEvent.click(screen.getByRole("button", { name: "Познакомиться" }));
  expect((await screen.findByTestId("companion-art")).getAttribute("data-stage")).toBe("1");
  expect(saved).toEqual({ appearance: "owl", name: "Луна", address: "vy" });
});

test("спутник: стадия, дни, одна реплика по обращению и открытка", async () => {
  stub({
    "GET /api/companion": () =>
      reply(
        200,
        companion({
          address: "vy",
          line: { hero: "companion", situation: "after_summary" },
          postcard: { code: "cbt_2", for_day: "2026-09-12" },
        }),
      ),
  });
  show(<CompanionCard />);
  expect((await screen.findByTestId("companion-stage")).textContent).toBe("Стадия 2: Подросток");
  expect(screen.getByTestId("companion-art").getAttribute("aria-label")).toContain("Лис");
  expect(screen.getByText("9 дней с дневником")).toBeTruthy(); // форма many (не «дня»)
  expect(screen.getByText("До следующей стадии осталось 12 дней")).toBeTruthy();
  expect(screen.getByTestId("companion-line").textContent).toContain("Итог дня сохранён");
  expect(screen.getByTestId("postcard").textContent).toContain(ru["hero.postcard.cbt_2"]);
});

test("дни и рост: формы множественного числа по count (one/few)", async () => {
  stub({
    "GET /api/companion": () => reply(200, companion({ days_total: 1, days_to_next: 1 })),
  });
  show(<CompanionCard />);
  await screen.findByTestId("companion-stage");
  expect(screen.getByText("1 день с дневником")).toBeTruthy();
  expect(screen.getByText("До следующей стадии остался 1 день")).toBeTruthy();
});

test("высшая стадия и отдых: черепаха, «некуда расти», повторный выбор облика", async () => {
  stub({
    "GET /api/companion": () =>
      reply(200, companion({ appearance: "turtle", stage: 5, days_to_next: null, resting: true })),
  });
  show(<CompanionCard />);
  const art = await screen.findByTestId("companion-art");
  expect(art.getAttribute("aria-label")).toContain("Черепаха");
  expect(screen.getByTestId("companion-stage").textContent).toBe("Стадия 5: Мудрец");
  expect(screen.getByText("Высшая стадия")).toBeTruthy();
  expect(screen.getByText("Луна отдыхает и никуда не торопится.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Изменить выбор" }));
  expect(await screen.findByTestId("companion-form")).toBeTruthy();
});

test("кит и новая стадия: реплика о росте помечается просмотренной", async () => {
  const fetchMock = stub({
    "GET /api/companion": () =>
      reply(
        200,
        companion({ appearance: "whale", line: { hero: "companion", situation: "new_stage" } }),
      ),
    "POST /api/companion/seen": () => reply(200, companion()),
  });
  show(<CompanionCard />);
  expect((await screen.findByTestId("companion-art")).getAttribute("aria-label")).toContain("Кит");
  expect(screen.getByTestId("companion-line").textContent).toContain("вырос");
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/companion/seen")).toBe(true),
  );
});

test("наставник: реплика только у открытого направления", async () => {
  stub({ "GET /api/companion": () => reply(200, companion({ address: "vy" })) });
  show(
    <>
      <MentorLine direction="cbt" />
      <MentorLine direction="act" />
    </>,
  );
  const line = await screen.findByTestId("mentor-line");
  expect(screen.getAllByTestId("mentor-line")).toHaveLength(1);
  expect(line.textContent).toContain("Аналитик");
  expect(line.textContent).toContain("вы");
});

test("кризис: ни реплик наставников, ни спутника", async () => {
  const fetchMock = stub({
    "GET /api/companion": () =>
      reply(200, companion({ line: { hero: "companion", situation: "return" } })),
  });
  show(
    <>
      <CompanionCard crisis />
      <MentorLine direction="cbt" crisis />
    </>,
  );
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  expect(screen.queryByTestId("companion")).toBeNull();
  expect(screen.queryByTestId("companion-line")).toBeNull();
  expect(screen.queryByTestId("mentor-line")).toBeNull();
  expect(screen.queryByTestId("mentor-art")).toBeNull();
});

test("запись с кризисным сигналом убирает спутника с главной", async () => {
  stub({
    "GET /api/companion": () =>
      reply(200, companion({ line: { hero: "companion", situation: "after_summary" } })),
    "GET /api/entries": () => reply(200, []),
    "POST /api/entries": () =>
      reply(201, {
        id: 2,
        date: "2026-09-29",
        text: "очень плохо",
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
  show(<HomePage advanced={false} />);
  expect(await screen.findByTestId("companion-line")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Что произошло и что вы чувствуете"), {
    target: { value: "очень плохо" },
  });
  fireEvent.click(screen.getByTestId("save-entry"));
  expect(await screen.findByTestId("help-block")).toBeTruthy();
  await waitFor(() => expect(screen.queryByTestId("companion")).toBeNull());
  expect(screen.queryByTestId("companion-line")).toBeNull();
});

test("тон реплик: без давления и вины", () => {
  const banned = /долж|опять|подвёл|подвел|снова пропустил|!/i;
  const lines = Object.entries(ru).filter(([key]) => key.startsWith("hero."));
  expect(lines.length).toBeGreaterThan(60);
  for (const [key, value] of lines) expect(value, key).not.toMatch(banned);
});
