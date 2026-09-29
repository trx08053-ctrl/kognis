// «Сегодня» приходит от сервера (/api/me → today, по часовому поясу профиля), а не из new Date():
// пояс браузера и пояс пользователя могут не совпадать (kognis-1yv).

import { useQuery } from "@tanstack/react-query";
import { getMe } from "./api";

// сдвиг календарной даты ISO (ГГГГ-ММ-ДД) на N дней; полдень исключает сдвиг из-за перехода на летнее время
export function shiftDay(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

// «сегодня» пользователя; вызывается только внутри авторизованного интерфейса, где /api/me уже загружен
export function useToday(): string {
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });
  if (!me.data) throw new Error("useToday вне авторизованного интерфейса");
  return me.data.today;
}

// IANA-пояс браузера для регистрации; null — сервер возьмёт пояс по умолчанию
export function browserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}
