// Клиент HTTP API бэкенда (/api/*). Типы повторяют схемы FastAPI (UserOut).

export interface User {
  id: number;
  name: string;
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(typeof body.detail === "string" ? body.detail : `ошибка ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function listUsers(): Promise<User[]> {
  return parse<User[]>(await fetch("/api/users"));
}

export async function createUser(name: string): Promise<User> {
  const response = await fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return parse<User>(response);
}
