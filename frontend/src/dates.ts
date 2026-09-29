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

// «сегодня» пользователя; в авторизованном интерфейсе /api/me уже загружен, пустая строка
// возможна только на миг при выходе (кэш очищен, компонент вот-вот размонтируется)
export function useToday(): string {
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });
  return me.data?.today ?? "";
}

// имена поясов для выбора в профиле; текущий пояс пользователя всегда в списке
export function timeZoneNames(current: string): string[] {
  const names = new Set<string>(Intl.supportedValuesOf("timeZone"));
  names.add(current);
  return [...names].sort();
}

// IANA-пояс браузера для регистрации; null — сервер возьмёт пояс по умолчанию
export function browserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}
