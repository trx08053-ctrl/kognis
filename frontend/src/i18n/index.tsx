// Мультиязычность интерфейса (docs/I18N.md): словари, t(), язык пользователя, Intl-форматирование.
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ru } from "./ru";

export const APP_NAME = "Kognis";

export type Key = keyof typeof ru;
// каждый язык обязан иметь все ключи базового словаря
export type Catalog = Record<Key, string>;
export type Params = Record<string, string | number>;

export type Locale = string;
export const LOCALES: readonly Locale[] = ["ru"];
export const DEFAULT_LOCALE: Locale = "ru";
export const LOCALE_NAMES: Record<Locale, string> = { ru: "Русский" };
const CATALOGS: Record<Locale, Catalog> = { ru };

export const LOCALE_KEY = "kognis-locale";
const RTL = new Set(["ar", "he", "fa", "ur"]);

export function direction(locale: string): "ltr" | "rtl" {
  return RTL.has(locale.split("-")[0] ?? "") ? "rtl" : "ltr";
}

function supported(tag: string | null | undefined, locales: readonly string[]): string | null {
  if (!tag) return null;
  const lower = tag.toLowerCase();
  return locales.find((l) => l === lower) ?? locales.find((l) => l === lower.split("-")[0]) ?? null;
}

// сохранённый выбор → язык браузера → язык по умолчанию
export function detectLocale(locales: readonly Locale[] = LOCALES): Locale {
  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(LOCALE_KEY);
  } catch {
    // хранилище недоступно — смотрим на браузер
  }
  const found =
    supported(stored, locales) ??
    (navigator.languages ?? [navigator.language]).map((l) => supported(l, locales)).find(Boolean);
  return found ?? DEFAULT_LOCALE;
}

export function isKey(value: string): value is Key {
  return Object.hasOwn(ru, value);
}

// форма множественного числа: `<ключ>.<категория Intl.PluralRules>`, иначе сам ключ
export function translate(catalog: Catalog, locale: string, key: Key, params?: Params): string {
  let text: string = catalog[key];
  if (typeof params?.count === "number") {
    const form = `${key}.${new Intl.PluralRules(locale).select(params.count)}`;
    const forms: Record<string, string> = catalog;
    text = forms[form] ?? text;
  }
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => String(params?.[name] ?? whole));
}

export function formatNumber(
  locale: string,
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

// календарная дата ISO (ГГГГ-ММ-ДД) форматируется как дата без пояса, остальное — как момент времени
export function formatDate(
  locale: string,
  value: string | Date,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Intl.DateTimeFormat(locale, { ...options, timeZone: "UTC" }).format(
      new Date(`${value}T12:00:00Z`),
    );
  }
  return new Intl.DateTimeFormat(locale, options).format(
    typeof value === "string" ? new Date(value) : value,
  );
}

export interface I18n {
  locale: Locale;
  locales: readonly string[];
  setLocale: (locale: Locale) => void;
  t: (key: Key, params?: Params) => string;
  formatDate: (value: string | Date, options?: Intl.DateTimeFormatOptions) => string;
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
}

function build(
  locale: Locale,
  setLocale: (locale: Locale) => void,
  catalogs: Record<string, Catalog>,
): I18n {
  const catalog = catalogs[locale] ?? ru;
  return {
    locale,
    locales: Object.keys(catalogs),
    setLocale,
    t: (key, params) => translate(catalog, locale, key, params),
    formatDate: (value, options) => formatDate(locale, value, options),
    formatNumber: (value, options) => formatNumber(locale, value, options),
  };
}

// без провайдера (изолированные компоненты) — язык по умолчанию
const I18nContext = createContext<I18n>(build(DEFAULT_LOCALE, () => {}, CATALOGS));

// catalogs — только для тестов: дополнительный язык, которого нет в LOCALES
export function I18nProvider({
  children,
  catalogs = CATALOGS,
  initial,
}: {
  children: ReactNode;
  catalogs?: Record<string, Catalog>;
  initial?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(
    () => initial ?? detectLocale(Object.keys(catalogs)),
  );
  const setLocale = useCallback((next: Locale) => {
    try {
      window.localStorage.setItem(LOCALE_KEY, next);
    } catch {
      // выбор действует до перезагрузки страницы
    }
    setLocaleState(next);
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = direction(locale);
  }, [locale]);
  const value = useMemo(() => build(locale, setLocale, catalogs), [locale, setLocale, catalogs]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  return useContext(I18nContext);
}
