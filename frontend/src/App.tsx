import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Navigate, Route, Routes } from "react-router";
import {
  ApiError,
  createEntry,
  type Entry,
  getMe,
  listEntries,
  login,
  logout,
  register,
  type User,
} from "./api";

const inputClass =
  "w-full rounded border border-slate-400 bg-white px-3 py-2 text-base text-slate-900";
const buttonClass =
  "rounded bg-indigo-700 px-4 py-2 text-base font-semibold text-white hover:bg-indigo-800";

function splitList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item !== "");
}

function ErrorMessage({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <p className="mt-2 text-red-800" role="alert">
      {error.message}
    </p>
  );
}

function AuthPage() {
  const client = useQueryClient();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const auth = useMutation({
    mutationFn: () => (mode === "login" ? login(email, password) : register(email, password)),
    onSuccess: (user) => client.setQueryData(["me"], user),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    auth.mutate();
  }

  return (
    <form className="space-y-4 rounded-lg border border-slate-300 bg-white p-4" onSubmit={submit}>
      <h2 className="text-xl font-semibold">{mode === "login" ? "Вход" : "Регистрация"}</h2>
      <div>
        <label htmlFor="email" className="mb-1 block font-semibold">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          className={inputClass}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="password" className="mb-1 block font-semibold">
          Пароль
        </label>
        <input
          id="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          required
          minLength={8}
          className={inputClass}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" className={buttonClass} data-testid="auth-submit">
          {mode === "login" ? "Войти" : "Зарегистрироваться"}
        </button>
        <button
          type="button"
          className="text-indigo-800 underline"
          onClick={() => {
            auth.reset();
            setMode(mode === "login" ? "register" : "login");
          }}
        >
          {mode === "login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти"}
        </button>
      </div>
      <ErrorMessage error={auth.error} />
    </form>
  );
}

function EntryForm() {
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [emotions, setEmotions] = useState("");
  const add = useMutation({
    mutationFn: () => createEntry({ text, tags: splitList(tags), emotions: splitList(emotions) }),
    onSuccess: () => {
      setText("");
      setTags("");
      setEmotions("");
      return client.invalidateQueries({ queryKey: ["entries"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <form className="space-y-4 rounded-lg border border-slate-300 bg-white p-4" onSubmit={submit}>
      <h2 className="text-xl font-semibold">Новая запись</h2>
      <div>
        <label htmlFor="text" className="mb-1 block font-semibold">
          Что произошло и что вы чувствуете
        </label>
        <textarea
          id="text"
          required
          rows={4}
          className={inputClass}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="tags" className="mb-1 block font-semibold">
          Теги (через запятую)
        </label>
        <input
          id="tags"
          className={inputClass}
          value={tags}
          onChange={(event) => setTags(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="emotions" className="mb-1 block font-semibold">
          Эмоции (через запятую)
        </label>
        <input
          id="emotions"
          className={inputClass}
          value={emotions}
          onChange={(event) => setEmotions(event.target.value)}
        />
      </div>
      <button type="submit" className={buttonClass} data-testid="save-entry">
        Сохранить
      </button>
      <ErrorMessage error={add.error} />
    </form>
  );
}

function EntryList() {
  const entries = useQuery({ queryKey: ["entries"], queryFn: listEntries });
  if (entries.isError) return <ErrorMessage error={entries.error} />;
  const items: Entry[] = entries.data ?? [];
  if (items.length === 0) return <p className="text-slate-700">Пока нет записей.</p>;
  return (
    <ul className="space-y-3" data-testid="entries">
      {items.map((entry) => (
        <li key={entry.id} className="rounded-lg border border-slate-300 bg-white p-4">
          <p className="text-sm text-slate-700">{entry.date}</p>
          <p className="whitespace-pre-wrap">{entry.text}</p>
          {(entry.tags.length > 0 || entry.emotions.length > 0) && (
            <p className="mt-2 text-sm text-slate-700">
              {[...entry.emotions, ...entry.tags.map((tag) => `#${tag}`)].join(" · ")}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function DiaryPage({ user }: { user: User }) {
  const client = useQueryClient();
  const out = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      client.clear();
      return client.invalidateQueries({ queryKey: ["me"] });
    },
  });
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p data-testid="whoami">{user.email}</p>
        <button type="button" className="text-indigo-800 underline" onClick={() => out.mutate()}>
          Выйти
        </button>
      </div>
      <EntryForm />
      <section aria-labelledby="entries-title" className="space-y-3">
        <h2 id="entries-title" className="text-xl font-semibold">
          Мои записи
        </h2>
        <EntryList />
      </section>
    </div>
  );
}

export function App() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });
  const user = me.data;
  const anonymous = me.error instanceof ApiError && me.error.status === 401;

  let body = <p>Загрузка…</p>;
  if (user) {
    body = (
      <Routes>
        <Route path="/" element={<DiaryPage user={user} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  } else if (anonymous) {
    body = (
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  } else if (me.isError) {
    body = <ErrorMessage error={me.error} />;
  }

  return (
    <main className="mx-auto my-10 max-w-2xl space-y-6 px-4">
      <h1 className="text-3xl font-bold">Kognis</h1>
      <p className="text-sm text-slate-700">
        Дневник переживаний. Это не медицинская помощь и не замена специалисту.
      </p>
      {body}
    </main>
  );
}
