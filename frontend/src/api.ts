// Клиент HTTP API бэкенда (/api/*). Типы повторяют схемы FastAPI (UserOut, EntryOut).
// Сессия — httpOnly cookie, её ставит и читает браузер; изменяющие запросы — только JSON (CSRF, ADR 0003).

export interface User {
  id: number;
  email: string;
}

export interface Entry {
  id: number;
  date: string;
  text: string;
  tags: string[];
  emotions: string[];
  protection: string;
}

export interface NewEntry {
  text: string;
  tags: string[];
  emotions: string[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    const detail = typeof body.detail === "string" ? body.detail : `ошибка ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function post<T>(url: string, body: unknown = {}): Promise<T> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((response) => parse<T>(response));
}

export const getMe = (): Promise<User> => fetch("/api/me").then((r) => parse<User>(r));
export const register = (email: string, password: string): Promise<User> =>
  post<User>("/api/auth/register", { email, password });
export const login = (email: string, password: string): Promise<User> =>
  post<User>("/api/auth/login", { email, password });
export const logout = (): Promise<void> => post<void>("/api/auth/logout");
export const listEntries = (): Promise<Entry[]> =>
  fetch("/api/entries").then((r) => parse<Entry[]>(r));
export const createEntry = (entry: NewEntry): Promise<Entry> => post<Entry>("/api/entries", entry);

export interface DayReview {
  id: number;
  date: string;
  wellbeing: number;
  mood: number;
  reflection: string;
}

export interface DayReviewInput {
  wellbeing: number;
  mood: number;
  reflection: string;
}

export const listDayReviews = (): Promise<DayReview[]> =>
  fetch("/api/day-reviews").then((r) => parse<DayReview[]>(r));
export const saveDayReview = (date: string, review: DayReviewInput): Promise<DayReview> =>
  fetch(`/api/day-reviews/${date}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(review),
  }).then((r) => parse<DayReview>(r));
