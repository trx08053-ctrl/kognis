// Страничные списки API: тело ответа — массив, курсор следующей страницы — заголовок X-Next-Cursor.
// Здесь только клиентская обвязка; типы записей и итогов — из схемы бэкенда (api.ts).

export interface Page<T> {
  items: T[];
  next: string | null;
}

export interface EntryQuery {
  limit?: number;
  cursor?: string | null;
  tag?: string;
  emotion?: string;
  from?: string;
  to?: string;
}

export function pageUrl(base: string, params: object): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `${base}?${text}` : base;
}

export function toPage<T>(items: T[], response: Response): Page<T> {
  return { items, next: response.headers.get("X-Next-Cursor") };
}
