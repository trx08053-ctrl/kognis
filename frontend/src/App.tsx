import { type FormEvent, useEffect, useState } from "react";
import { createUser, listUsers, type User } from "./api";

export function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listUsers().then(setUsers, (err: unknown) => setError(String(err)));
  }, []);

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const user = await createUser(name);
      setUsers((current) => [...current, user]);
      setName("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <main>
      <h1>Kognis</h1>
      <form className="card" onSubmit={register}>
        <label htmlFor="name">Имя пользователя</label>
        <div className="row">
          <input
            id="name"
            name="name"
            autoComplete="name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" data-testid="register">
            Добавить
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </form>
      <h2>Пользователи</h2>
      {users.length > 0 ? (
        <ul className="users" data-testid="users">
          {users.map((user) => (
            <li key={user.id}>{user.name}</li>
          ))}
        </ul>
      ) : (
        <p className="empty">Пока никого нет.</p>
      )}
    </main>
  );
}
