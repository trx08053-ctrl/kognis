import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

function renderAnonymous(path = "/") {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: "нужен вход" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    ),
  );
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

test("гость видит лендинг со всеми разделами и формой входа", async () => {
  renderAnonymous("/day");
  expect(
    await screen.findByRole("heading", { level: 1, name: /первый шаг к спокойствию/ }),
  ).toBeTruthy();
  for (const name of [
    "Всё, чтобы лучше понимать себя",
    "Три шага от переживания к ясности",
    "Изменения, которые видно на графике",
    "Небольшие шаги — заметные перемены",
    "Читайте о психологии просто",
    "Частые вопросы",
  ]) {
    expect(screen.getByRole("heading", { level: 2, name })).toBeTruthy();
  }
  expect(screen.getByRole("heading", { name: "Вход" })).toBeTruthy();
  expect(screen.getByTestId("landing-disclaimer").textContent).toContain("112");
});

test("кнопки «Начать» переключают форму на регистрацию", async () => {
  renderAnonymous();
  fireEvent.click(await screen.findByTestId("cta-hero"));
  expect(screen.getByRole("heading", { name: "Регистрация" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Уже есть аккаунт? Войти" }));
  expect(screen.getByRole("heading", { name: "Вход" })).toBeTruthy();
  fireEvent.click(screen.getByTestId("cta-final"));
  expect(screen.getByRole("heading", { name: "Регистрация" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Войти" }));
  expect(screen.getByRole("heading", { name: "Вход" })).toBeTruthy();
  fireEvent.click(screen.getByTestId("cta-header"));
  expect(screen.getByRole("heading", { name: "Регистрация" })).toBeTruthy();
});

test("демо: вкладки направлений мышью и с клавиатуры", async () => {
  renderAnonymous();
  const lens = await screen.findByTestId("demo-lens");
  expect(lens.textContent).toContain("Чтение мыслей");
  fireEvent.click(screen.getByRole("tab", { name: "ACT" }));
  expect(screen.getByTestId("demo-lens").textContent).toContain("Слияние с мыслью");
  const tablist = screen.getByRole("tablist");
  fireEvent.keyDown(tablist, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Схема-терапия" }).getAttribute("aria-selected")).toBe(
    "true",
  );
  fireEvent.keyDown(tablist, { key: "End" });
  expect(screen.getByTestId("demo-lens").textContent).toContain("Избегание снижает тревогу");
  fireEvent.keyDown(tablist, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "КПТ" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(tablist, { key: "ArrowLeft" });
  fireEvent.keyDown(tablist, { key: "Home" });
  expect(screen.getByRole("tab", { name: "КПТ" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(tablist, { key: "a" });
  expect(screen.getByRole("tab", { name: "КПТ" }).getAttribute("aria-selected")).toBe("true");
});

test("график: переключение показателя", async () => {
  renderAnonymous();
  expect((await screen.findByTestId("metric-delta")).textContent).toBe("+2,3 балла");
  fireEvent.click(screen.getByRole("button", { name: "Самочувствие" }));
  expect(screen.getByTestId("metric-delta").textContent).toBe("+1,8 балла");
  expect(screen.getByRole("button", { name: "Самочувствие" }).getAttribute("aria-pressed")).toBe(
    "true",
  );
  expect(screen.getByRole("img", { name: /График «Самочувствие»/ })).toBeTruthy();
});

test("истории листаются вперёд, назад и по точкам", async () => {
  renderAnonymous();
  const story = () => screen.getByTestId("story").textContent ?? "";
  expect(await screen.findByTestId("story")).toBeTruthy();
  expect(story()).toContain("Алексей");
  fireEvent.click(screen.getByRole("button", { name: "Следующая история" }));
  expect(story()).toContain("Марина");
  fireEvent.click(screen.getByRole("button", { name: "Предыдущая история" }));
  fireEvent.click(screen.getByRole("button", { name: "Предыдущая история" }));
  expect(story()).toContain("Даша");
  fireEvent.click(screen.getByRole("button", { name: /История 1/ }));
  expect(story()).toContain("Алексей");
});

test("статья открывается и закрывается", async () => {
  renderAnonymous();
  const buttons = await screen.findAllByRole("button", { name: /Читать статью/ });
  expect(buttons).toHaveLength(3);
  const first = buttons[0];
  if (!first) throw new Error("нет кнопки статьи");
  fireEvent.click(first);
  const article = screen.getByTestId("article");
  expect(within(article).getByRole("heading", { name: /записывать эмоции/ })).toBeTruthy();
  fireEvent.click(within(article).getByRole("button", { name: "Закрыть статью" }));
  expect(screen.queryByTestId("article")).toBeNull();
});

test("смена темы на лендинге", async () => {
  renderAnonymous();
  const toggle = await screen.findByTestId("theme-toggle");
  const before = document.documentElement.classList.contains("dark");
  fireEvent.click(toggle);
  expect(document.documentElement.classList.contains("dark")).toBe(!before);
  fireEvent.click(toggle);
  expect(document.documentElement.classList.contains("dark")).toBe(before);
});
