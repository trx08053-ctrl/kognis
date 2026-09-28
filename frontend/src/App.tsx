import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router";
import {
  ApiError,
  createEntry,
  type DayReview,
  type Entry,
  getMe,
  type HelpBlock,
  listDayReviews,
  listEntries,
  login,
  logout,
  register,
  saveDayReview,
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

function HelpPanel({ help }: { help: HelpBlock }) {
  return (
    <section
      role="alert"
      aria-labelledby="help-title"
      data-testid="help-block"
      className="rounded-lg border-2 border-red-800 bg-red-50 p-4 text-red-950"
    >
      <h3 id="help-title" className="text-lg font-bold">
        Вам может понадобиться помощь
      </h3>
      <p className="mt-1">{help.message}</p>
      <ul className="mt-2 space-y-1">
        {help.contacts.map((contact) => (
          <li key={`${contact.name}-${contact.phone}`}>
            {contact.name}:{" "}
            <a href={`tel:${contact.phone}`} className="text-xl font-bold underline">
              {contact.phone}
            </a>
            {contact.note && <span> — {contact.note}</span>}
          </li>
        ))}
      </ul>
    </section>
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
      {add.data?.help && <HelpPanel help={add.data.help} />}
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

function localToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function DayReviewForm() {
  const client = useQueryClient();
  const [date, setDate] = useState(localToday);
  const [wellbeing, setWellbeing] = useState("5");
  const [mood, setMood] = useState("5");
  const [reflection, setReflection] = useState("");
  const save = useMutation({
    mutationFn: () =>
      saveDayReview(date, { wellbeing: Number(wellbeing), mood: Number(mood), reflection }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["day-reviews"] }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate();
  }

  return (
    // noValidate: границы 1–10 проверяет сервер, ошибка показывается в интерфейсе
    <form
      className="space-y-4 rounded-lg border border-slate-300 bg-white p-4"
      onSubmit={submit}
      noValidate
    >
      <h2 className="text-xl font-semibold">Итог дня</h2>
      <div>
        <label htmlFor="review-date" className="mb-1 block font-semibold">
          Дата
        </label>
        <input
          id="review-date"
          type="date"
          required
          className={inputClass}
          value={date}
          onChange={(event) => setDate(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="wellbeing" className="mb-1 block font-semibold">
          Самочувствие (1–10)
        </label>
        <input
          id="wellbeing"
          type="number"
          min={1}
          max={10}
          step={1}
          className={inputClass}
          value={wellbeing}
          onChange={(event) => setWellbeing(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="mood" className="mb-1 block font-semibold">
          Настроение (1–10)
        </label>
        <input
          id="mood"
          type="number"
          min={1}
          max={10}
          step={1}
          className={inputClass}
          value={mood}
          onChange={(event) => setMood(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="reflection" className="mb-1 block font-semibold">
          Рефлексия: что запомнилось сегодня
        </label>
        <textarea
          id="reflection"
          rows={3}
          className={inputClass}
          value={reflection}
          onChange={(event) => setReflection(event.target.value)}
        />
      </div>
      <button type="submit" className={buttonClass} data-testid="save-review">
        Сохранить итог
      </button>
      {save.isSuccess && (
        <p className="mt-2 text-green-900" role="status">
          Итог за {save.data.date} сохранён.
        </p>
      )}
      <ErrorMessage error={save.error} />
    </form>
  );
}

function DayReviewHistory() {
  const reviews = useQuery({ queryKey: ["day-reviews"], queryFn: listDayReviews });
  if (reviews.isError) return <ErrorMessage error={reviews.error} />;
  const items: DayReview[] = reviews.data ?? [];
  if (items.length === 0) return <p className="text-slate-700">Пока нет итогов дня.</p>;
  return (
    <ul className="space-y-3" data-testid="reviews">
      {items.map((review) => (
        <li key={review.id} className="rounded-lg border border-slate-300 bg-white p-4">
          <p className="text-sm text-slate-700">{review.date}</p>
          <p>
            Самочувствие: {review.wellbeing} · Настроение: {review.mood}
          </p>
          {review.reflection && <p className="whitespace-pre-wrap">{review.reflection}</p>}
        </li>
      ))}
    </ul>
  );
}

function DayReviewPage() {
  return (
    <div className="space-y-6">
      <DayReviewForm />
      <section aria-labelledby="reviews-title" className="space-y-3">
        <h2 id="reviews-title" className="text-xl font-semibold">
          История итогов
        </h2>
        <DayReviewHistory />
      </section>
    </div>
  );
}

function Shell({ user, children }: { user: User; children: ReactNode }) {
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
      <nav aria-label="Разделы" className="flex gap-4">
        <Link to="/" className="text-indigo-800 underline">
          Дневник
        </Link>
        <Link to="/day" className="text-indigo-800 underline">
          Итог дня
        </Link>
      </nav>
      {children}
      <p className="border-t border-slate-300 pt-3 text-sm text-slate-700" data-testid="disclaimer">
        Kognis — не медицинская помощь и не заменяет специалиста. В кризисной ситуации звоните 112.
      </p>
    </div>
  );
}

function DiaryPage() {
  return (
    <div className="space-y-6">
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
        <Route
          path="/"
          element={
            <Shell user={user}>
              <DiaryPage />
            </Shell>
          }
        />
        <Route
          path="/day"
          element={
            <Shell user={user}>
              <DayReviewPage />
            </Shell>
          }
        />
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
