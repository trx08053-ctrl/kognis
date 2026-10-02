// Мотивация 2.0 (4/4): искры — витрина, покупка и аксессуар на спутнике; при кризисе блока нет.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { CompanionArt, CompanionCard } from "./components/Heroes";
import { SparksPanel } from "./components/Sparks";
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

const FREEZE_NOTE = "запас всегда не больше";

test("витрина: баланс, цены и заморозка с пометкой о капе", async () => {
  stub({
    "GET /api/sparks": () =>
      reply(200, {
        balance: 40,
        freezes: 2,
        catalog: [
          { code: "scarf", kind: "accessory", price: 50, owned: false },
          { code: "freeze", kind: "freeze", price: 30, owned: false },
        ],
      }),
  });
  show(<SparksPanel />);
  expect((await screen.findByTestId("sparks-balance")).textContent).toBe("40 искр");
  expect(screen.getByTestId("shop-scarf").textContent).toContain(ru["spark.item.scarf"]);
  expect(screen.getByTestId("shop-freeze").textContent).toContain(FREEZE_NOTE);
});

test("покупка: списывается баланс, товар отмечается купленным", async () => {
  const fetchMock = stub({
    "GET /api/sparks": () =>
      reply(200, {
        balance: 100,
        freezes: 2,
        catalog: [{ code: "scarf", kind: "accessory", price: 50, owned: false }],
      }),
    "POST /api/sparks/purchase": () =>
      reply(200, {
        balance: 50,
        freezes: 2,
        catalog: [{ code: "scarf", kind: "accessory", price: 50, owned: true }],
      }),
  });
  show(<SparksPanel />);
  fireEvent.click(await screen.findByRole("button", { name: ru["spark.buy"] }));
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/sparks/purchase")).toBe(true),
  );
  expect(await screen.findByTestId("shop-scarf-owned")).toBeTruthy();
});

test("недостаток искр: ошибка по коду показывается, покупка не проходит", async () => {
  stub({
    "GET /api/sparks": () =>
      reply(200, {
        balance: 10,
        freezes: 2,
        catalog: [{ code: "hat", kind: "accessory", price: 50, owned: false }],
      }),
    "POST /api/sparks/purchase": () =>
      reply(409, { detail: { code: "sparks.not_enough", params: {} } }),
  });
  show(<SparksPanel />);
  fireEvent.click(await screen.findByRole("button", { name: ru["spark.buy"] }));
  expect(await screen.findByText(ru["error.sparks.not_enough"])).toBeTruthy();
});

test("аксессуар после покупки виден на спутнике", async () => {
  const companion = {
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
    mentors: [],
  };
  stub({
    "GET /api/sparks": () =>
      reply(200, {
        balance: 50,
        freezes: 2,
        catalog: [{ code: "scarf", kind: "accessory", price: 50, owned: true }],
      }),
    "GET /api/companion": () => reply(200, companion),
  });
  show(<CompanionCard />);
  const art = await screen.findByTestId("companion-art");
  await waitFor(() => expect(art.getAttribute("data-accessory")).toBe("scarf"));
  expect(screen.getByTestId("companion-accessory")).toBeTruthy();
});

test("каждый аксессуар каталога рисуется на спутнике", () => {
  for (const code of ["scarf", "hat", "backpack"]) {
    const { unmount } = render(
      <CompanionArt appearance="fox" stage={3} label="тест" accessory={code} />,
    );
    expect(screen.getByTestId("companion-accessory")).toBeTruthy();
    expect(screen.getByTestId("companion-art").getAttribute("data-accessory")).toBe(code);
    unmount();
  }
});

test("купленный фон рисуется за спутником", () => {
  for (const code of ["bg_stars", "bg_forest"]) {
    const { unmount } = render(
      <CompanionArt appearance="owl" stage={2} label="тест" background={code} />,
    );
    expect(screen.getByTestId("companion-background")).toBeTruthy();
    expect(screen.getByTestId("companion-art").getAttribute("data-background")).toBe(code);
    unmount();
  }
});

test("купленный фон виден на карточке спутника целиком (владение → рендер)", async () => {
  const companion = {
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
    mentors: [],
  };
  stub({
    "GET /api/sparks": () =>
      reply(200, {
        balance: 0,
        freezes: 2,
        catalog: [{ code: "bg_stars", kind: "background", price: 75, owned: true }],
      }),
    "GET /api/companion": () => reply(200, companion),
  });
  show(<CompanionCard />);
  const art = await screen.findByTestId("companion-art");
  await waitFor(() => expect(art.getAttribute("data-background")).toBe("bg_stars"));
  expect(screen.getByTestId("companion-background")).toBeTruthy();
});

test("неизвестный код товара не ломает витрину", async () => {
  stub({
    "GET /api/sparks": () =>
      reply(200, {
        balance: 0,
        freezes: 2,
        catalog: [{ code: "mystery", kind: "accessory", price: 10, owned: false }],
      }),
  });
  show(<SparksPanel />);
  expect(await screen.findByTestId("shop-mystery")).toBeTruthy();
  expect(screen.getByTestId("shop-mystery").textContent).not.toContain("undefined");
});

test("кризис: блока искр нет", () => {
  stub({ "GET /api/sparks": () => reply(200, { balance: 5, freezes: 2, catalog: [] }) });
  show(<SparksPanel crisis />);
  expect(screen.queryByTestId("sparks")).toBeNull();
});
