// Тема оформления: по умолчанию как в системе, явный выбор пользователя хранится в браузере.
import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

export const THEME_KEY = "kognis-theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function systemTheme(): Theme {
  return window.matchMedia?.(DARK_QUERY).matches ? "dark" : "light";
}

export function storedTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null; // хранилище недоступно — остаёмся на системной теме
  }
}

export function currentTheme(): Theme {
  return storedTheme() ?? systemTheme();
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY);
    if (!media) return;
    // смена системной темы подхватывается, пока пользователь не выбрал тему сам
    const onChange = () => {
      if (storedTheme() === null) setTheme(systemTheme());
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // выбор действует до перезагрузки страницы
    }
    setTheme(next);
  };
  return [theme, toggle];
}
