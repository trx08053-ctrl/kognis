import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { ErrorMessage } from "./components/ErrorMessage";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { Shell } from "./components/Shell";
import {
  type Catalog,
  detectLocale,
  formatDate,
  formatNumber,
  I18nProvider,
  isKey,
  LOCALE_KEY,
  translate,
  useI18n,
} from "./i18n";
import { ru } from "./i18n/ru";

// тестовый второй язык живёт только здесь: в LOCALES его нет (переводы — отдельные задачи)
const test_en: Catalog = {
  ...ru,
  "shell.logout": "Log out",
  "shell.nav.diary": "Diary",
  "shell.theme_dark": "Dark theme",
  "shell.theme_light": "Light theme",
  "shell.disclaimer": "Not medical help.",
};

const user = { email: "ann@example.com" } as never;

function Switch() {
  const { setLocale } = useI18n();
  return (
    <button type="button" onClick={() => setLocale("en")}>
      to-en
    </button>
  );
}

function renderShell() {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() => Promise.resolve(new Response("{}", { status: 500 }))),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <I18nProvider catalogs={{ ru, en: test_en }} initial="ru">
        <MemoryRouter>
          <Switch />
          <Shell user={user}>
            <p>content</p>
          </Shell>
        </MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  document.documentElement.removeAttribute("lang");
  document.documentElement.removeAttribute("dir");
});

// @acceptance kognis-i7j AC2
test("смена языка переключает тексты Shell без перезагрузки и меняет <html lang>", async () => {
  renderShell();
  expect(screen.getByTestId("disclaimer").textContent).toContain("не медицинская помощь");
  expect(screen.getByRole("button", { name: "Выйти" })).toBeTruthy();
  expect(document.documentElement.lang).toBe("ru");
  expect(document.documentElement.dir).toBe("ltr");

  await act(async () => screen.getByRole("button", { name: "to-en" }).click());

  expect(screen.getByRole("button", { name: "Log out" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Diary" })).toBeTruthy();
  expect(screen.getByTestId("disclaimer").textContent).toBe("Not medical help.");
  expect(document.documentElement.lang).toBe("en");
  expect(window.localStorage.getItem(LOCALE_KEY)).toBe("en");
});

// @acceptance kognis-i7j AC3
test("даты и числа форматируются по языку через Intl", () => {
  expect(formatDate("ru", "2026-01-05", { day: "2-digit", month: "2-digit" })).toBe("05.01");
  expect(formatDate("en-US", "2026-01-05", { day: "2-digit", month: "2-digit" })).toBe("01/05");
  expect(formatDate("ru", "2026-01-05", { dateStyle: "long" })).toBe("5 января 2026 г.");
  expect(formatDate("en-US", "2026-01-05", { dateStyle: "long" })).toBe("January 5, 2026");
  expect(formatNumber("ru", 1234.5)).toBe("1 234,5");
  expect(formatNumber("en-US", 1234.5)).toBe("1,234.5");
});

test("параметры и формы множественного числа подставляются по языку", () => {
  const catalog = {
    ...ru,
    "shell.level": "{level} уровень",
    "shell.streak.one": "{count} день",
    "shell.streak.few": "{count} дня",
    "shell.streak.many": "{count} дней",
  } as Catalog;
  expect(translate(catalog, "ru", "shell.level", { level: 3 })).toBe("3 уровень");
  const days = (count: number) => translate(catalog, "ru", "shell.streak", { count });
  expect([days(1), days(3), days(5), days(21)]).toEqual(["1 день", "3 дня", "5 дней", "21 день"]);
});

test("язык по умолчанию: сохранённый → браузер → ru; isKey отличает ключи от текста", () => {
  const locales = ["ru", "en"];
  vi.spyOn(navigator, "languages", "get").mockReturnValue(["en-GB", "ru"]);
  expect(detectLocale(locales)).toBe("en");
  window.localStorage.setItem(LOCALE_KEY, "ru");
  expect(detectLocale(locales)).toBe("ru");
  window.localStorage.clear();
  expect(detectLocale(["ru"])).toBe("ru");
  vi.restoreAllMocks();
  expect(isKey("shell.logout")).toBe(true);
  expect(isKey("Выйти")).toBe(false);
});

test("язык справа налево выставляет dir=rtl", () => {
  render(
    <I18nProvider catalogs={{ ru, ar: test_en }} initial="ar">
      <p>x</p>
    </I18nProvider>,
  );
  expect(document.documentElement.dir).toBe("rtl");
});

test("переключатель языка виден при двух языках и меняет язык; при одном — скрыт", async () => {
  const { unmount } = render(
    <I18nProvider catalogs={{ ru, en: test_en }} initial="ru">
      <LanguageSwitcher />
    </I18nProvider>,
  );
  const select = screen.getByTestId("language-select") as HTMLSelectElement;
  await act(async () => fireEvent.change(select, { target: { value: "en" } }));
  expect(select.value).toBe("en");
  expect(document.documentElement.lang).toBe("en");
  unmount();
  render(<LanguageSwitcher />);
  expect(screen.queryByTestId("language-select")).toBeNull();
});

test("ErrorMessage переводит ключ словаря и оставляет готовый текст как есть", () => {
  render(<ErrorMessage error={new Error("error.private.wrong_password")} />);
  expect(screen.getByRole("alert").textContent).toContain("Неверный пароль");
  cleanup();
  render(<ErrorMessage error={new Error("Готовый текст сервера")} />);
  expect(screen.getByRole("alert").textContent).toBe("Готовый текст сервера");
  cleanup();
  render(<ErrorMessage error={null} />);
  expect(screen.queryByRole("alert")).toBeNull();
});

test("formatDate принимает момент времени; без хранилища язык берётся из браузера", () => {
  const utc = { dateStyle: "medium", timeZone: "UTC" } as const;
  expect(formatDate("en-US", new Date("2026-01-05T12:00:00Z"), utc)).toBe("Jan 5, 2026");
  expect(formatDate("en-US", "2026-01-05T12:00:00Z", utc)).toBe("Jan 5, 2026");
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  expect(detectLocale(["ru", "en"])).toBeTypeOf("string");
  render(
    <I18nProvider catalogs={{ ru, en: test_en }} initial="ru">
      <Switch />
    </I18nProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "to-en" }));
  expect(document.documentElement.lang).toBe("en");
  vi.restoreAllMocks();
});
