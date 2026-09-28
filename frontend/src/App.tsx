import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router";
import {
  type Analysis,
  ApiError,
  acceptQuestFromAnalysis,
  answerAnalysis,
  createEntry,
  type DayReview,
  type Direction,
  type Entry,
  getMe,
  getMood,
  getProgress,
  type HelpBlock,
  listDayReviews,
  listDirections,
  listEntries,
  login,
  logout,
  openEntry,
  register,
  runAnalysis,
  saveDayReview,
  saveSettings,
  type User,
} from "./api";
import { MoodChart } from "./Charts";
import { decryptText, encryptText, MIN_PRIVATE_PASSWORD } from "./privateCrypto";
import { QuestsPage } from "./Quests";
import { useTheme } from "./theme";

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
  const [locked, setLocked] = useState(false);
  const [lockPassword, setLockPassword] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [privatePassword, setPrivatePassword] = useState("");
  const [privateRepeat, setPrivateRepeat] = useState("");
  const add = useMutation({
    mutationFn: async () => {
      const labels = { tags: splitList(tags), emotions: splitList(emotions) };
      if (!isPrivate) {
        return createEntry({
          text,
          ...labels,
          ...(locked ? { protection: "locked", lock_password: lockPassword } : {}),
        });
      }
      if (privatePassword !== privateRepeat) throw new Error("Пароли не совпадают");
      // шифруем здесь: открытый текст и пароль не покидают устройство
      const cipher = await encryptText(privatePassword, text.trim());
      return createEntry({ text: "", ...labels, protection: "private", cipher });
    },
    onSuccess: () => {
      setText("");
      setTags("");
      setEmotions("");
      setLocked(false);
      setLockPassword("");
      setIsPrivate(false);
      setPrivatePassword("");
      setPrivateRepeat("");
      void client.invalidateQueries({ queryKey: ["progress"] });
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
      <div>
        <label className="flex items-center gap-2 font-semibold">
          <input
            type="checkbox"
            checked={isPrivate}
            onChange={(event) => {
              setIsPrivate(event.target.checked);
              if (event.target.checked) setLocked(false);
            }}
          />
          Приватная запись (шифруется на этом устройстве)
        </label>
        {isPrivate && (
          <div className="mt-2 space-y-2">
            <p
              className="rounded border border-amber-700 bg-amber-50 p-2 text-amber-900"
              data-testid="private-warning"
            >
              Текст зашифруется в браузере, сервер и ИИ его не прочитают. Пароль нигде не хранится и
              восстановить его нельзя: забудете пароль — запись будет потеряна навсегда. Теги,
              эмоции и дата не шифруются — не пишите в них ничего личного.
            </p>
            <label htmlFor="private-password" className="mb-1 block">
              Пароль записи (от {MIN_PRIVATE_PASSWORD} символов)
            </label>
            <input
              id="private-password"
              type="password"
              required
              minLength={MIN_PRIVATE_PASSWORD}
              autoComplete="new-password"
              className={inputClass}
              value={privatePassword}
              onChange={(event) => setPrivatePassword(event.target.value)}
            />
            <label htmlFor="private-repeat" className="mb-1 block">
              Повторите пароль
            </label>
            <input
              id="private-repeat"
              type="password"
              required
              autoComplete="new-password"
              className={inputClass}
              value={privateRepeat}
              onChange={(event) => setPrivateRepeat(event.target.value)}
            />
          </div>
        )}
      </div>
      <div>
        <label className="flex items-center gap-2 font-semibold">
          <input
            type="checkbox"
            checked={locked}
            disabled={isPrivate}
            onChange={(event) => setLocked(event.target.checked)}
          />
          Закрыть запись замком
        </label>
        {locked && (
          <div className="mt-2">
            <label htmlFor="lock-password" className="mb-1 block">
              Пароль замка (от 8 символов). Забытый пароль восстановить нельзя.
            </label>
            <input
              id="lock-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className={inputClass}
              value={lockPassword}
              onChange={(event) => setLockPassword(event.target.value)}
            />
          </div>
        )}
      </div>
      <button type="submit" className={buttonClass} data-testid="save-entry">
        Сохранить
      </button>
      <ErrorMessage error={add.error} />
      {add.data?.help && <HelpPanel help={add.data.help} />}
    </form>
  );
}

function LockedEntryBody({ entry }: { entry: Entry }) {
  // текст открытой записи живёт только в состоянии компонента — не в кэше запросов
  const [password, setPassword] = useState("");
  const [opened, setOpened] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: () => openEntry(entry.id, password),
    onSuccess: (result) => {
      setOpened(result.text);
      setPassword("");
    },
  });

  if (opened !== null) {
    return (
      <>
        <p className="whitespace-pre-wrap" data-testid="opened-text">
          {opened}
        </p>
        <button
          type="button"
          className="mt-2 text-indigo-800 underline"
          onClick={() => setOpened(null)}
        >
          Скрыть
        </button>
      </>
    );
  }
  return (
    <form
      className="space-y-2"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        open.mutate();
      }}
    >
      <p data-testid="locked-stub">🔒 Запись закрыта замком</p>
      <label htmlFor={`open-${entry.id}`} className="block text-sm">
        Пароль замка
      </label>
      <input
        id={`open-${entry.id}`}
        type="password"
        required
        autoComplete="off"
        className={inputClass}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" className={buttonClass}>
        Открыть
      </button>
      <ErrorMessage error={open.error} />
    </form>
  );
}

function PrivateEntryBody({ entry }: { entry: Entry }) {
  // расшифровка целиком в браузере; открытый текст — только в состоянии компонента
  const [password, setPassword] = useState("");
  const [opened, setOpened] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: () => {
      if (!entry.cipher) throw new Error("В записи нет шифртекста");
      return decryptText(password, entry.cipher);
    },
    onSuccess: (text) => {
      setOpened(text);
      setPassword("");
    },
  });

  if (opened !== null) {
    return (
      <>
        <p className="whitespace-pre-wrap" data-testid="private-text">
          {opened}
        </p>
        <button
          type="button"
          className="mt-2 text-indigo-800 underline"
          onClick={() => setOpened(null)}
        >
          Скрыть
        </button>
      </>
    );
  }
  return (
    <form
      className="space-y-2"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        open.mutate();
      }}
    >
      <p data-testid="private-stub">🔐 Приватная запись — расшифровывается на этом устройстве</p>
      <label htmlFor={`private-open-${entry.id}`} className="block text-sm">
        Пароль записи
      </label>
      <input
        id={`private-open-${entry.id}`}
        type="password"
        required
        autoComplete="off"
        className={inputClass}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" className={buttonClass}>
        Расшифровать
      </button>
      <ErrorMessage error={open.error} />
    </form>
  );
}

interface EntryFilters {
  tag: string;
  emotion: string;
  from: string;
  to: string;
}

const NO_FILTERS: EntryFilters = { tag: "", emotion: "", from: "", to: "" };

function matchesFilters(entry: Entry, f: EntryFilters): boolean {
  return (
    (f.tag === "" || entry.tags.includes(f.tag)) &&
    (f.emotion === "" || entry.emotions.includes(f.emotion)) &&
    (f.from === "" || entry.date >= f.from) &&
    (f.to === "" || entry.date <= f.to)
  );
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, "ru"));
}

function EntryFilterBar({
  entries,
  filters,
  onChange,
}: {
  entries: Entry[];
  filters: EntryFilters;
  onChange: (next: EntryFilters) => void;
}) {
  const tags = uniqueSorted(entries.flatMap((entry) => entry.tags));
  const emotions = uniqueSorted(entries.flatMap((entry) => entry.emotions));
  return (
    <form
      aria-label="Фильтры записей"
      data-testid="entry-filters"
      className="grid gap-3 rounded-lg border border-slate-300 bg-white p-4 sm:grid-cols-2"
      onSubmit={(event) => event.preventDefault()}
    >
      <div>
        <label htmlFor="filter-tag" className="mb-1 block">
          Тег
        </label>
        <select
          id="filter-tag"
          className={inputClass}
          value={filters.tag}
          onChange={(event) => onChange({ ...filters, tag: event.target.value })}
        >
          <option value="">Все теги</option>
          {tags.map((tag) => (
            <option key={tag} value={tag}>
              #{tag}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="filter-emotion" className="mb-1 block">
          Эмоция
        </label>
        <select
          id="filter-emotion"
          className={inputClass}
          value={filters.emotion}
          onChange={(event) => onChange({ ...filters, emotion: event.target.value })}
        >
          <option value="">Все эмоции</option>
          {emotions.map((emotion) => (
            <option key={emotion} value={emotion}>
              {emotion}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="filter-from" className="mb-1 block">
          С даты
        </label>
        <input
          id="filter-from"
          type="date"
          lang="ru"
          className={inputClass}
          value={filters.from}
          onChange={(event) => onChange({ ...filters, from: event.target.value })}
        />
      </div>
      <div>
        <label htmlFor="filter-to" className="mb-1 block">
          По дату
        </label>
        <input
          id="filter-to"
          type="date"
          lang="ru"
          className={inputClass}
          value={filters.to}
          onChange={(event) => onChange({ ...filters, to: event.target.value })}
        />
      </div>
    </form>
  );
}

const RECENT_LIMIT = 5;

// простой режим — последние записи; Advanced — все записи с фильтрами
function EntryList({ advanced }: { advanced: boolean }) {
  const [filters, setFilters] = useState<EntryFilters>(NO_FILTERS);
  const entries = useQuery({ queryKey: ["entries"], queryFn: listEntries });
  if (entries.isError) return <ErrorMessage error={entries.error} />;
  const all: Entry[] = entries.data ?? [];
  if (all.length === 0) return <p className="text-slate-700">Пока нет записей.</p>;
  const items = advanced
    ? all.filter((entry) => matchesFilters(entry, filters))
    : all.slice(0, RECENT_LIMIT);
  return (
    <>
      {advanced && <EntryFilterBar entries={all} filters={filters} onChange={setFilters} />}
      {items.length === 0 ? (
        <p className="text-slate-700">По фильтрам ничего не найдено.</p>
      ) : (
        <EntryItems items={items} />
      )}
    </>
  );
}

function EntryItems({ items }: { items: Entry[] }) {
  return (
    <ul className="space-y-3" data-testid="entries">
      {items.map((entry) => (
        <li key={entry.id} className="rounded-lg border border-slate-300 bg-white p-4">
          <p className="text-sm text-slate-700">{entry.date}</p>
          {entry.protection === "locked" && <LockedEntryBody entry={entry} />}
          {entry.protection === "private" && <PrivateEntryBody entry={entry} />}
          {entry.protection !== "locked" && entry.protection !== "private" && (
            <p className="whitespace-pre-wrap">{entry.text}</p>
          )}
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

interface ScaleFieldProps {
  id: string;
  label: string;
  low: string;
  high: string;
  value: string;
  onChange: (value: string) => void;
}

// шкала 1–10: ползунок с подписями концов и текущим значением
function ScaleField({ id, label, low, high, value, onChange }: ScaleFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 flex items-baseline justify-between font-semibold">
        {label}
        <output htmlFor={id} className="text-2xl text-indigo-800">
          {value}
        </output>
      </label>
      <input
        id={id}
        type="range"
        min={1}
        max={10}
        step={1}
        className="w-full accent-indigo-700"
        aria-describedby={`${id}-hint`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <div id={`${id}-hint`} className="flex justify-between text-sm text-slate-700">
        <span>1 · {low}</span>
        <span>{high} · 10</span>
      </div>
    </div>
  );
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
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["progress"] });
      return client.invalidateQueries({ queryKey: ["day-reviews"] });
    },
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
      <ScaleField
        id="wellbeing"
        label="Самочувствие (1–10)"
        low="плохо"
        high="отлично"
        value={wellbeing}
        onChange={setWellbeing}
      />
      <ScaleField
        id="mood"
        label="Настроение (1–10)"
        low="тяжёлое"
        high="радостное"
        value={mood}
        onChange={setMood}
      />
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
      {save.data?.help && <HelpPanel help={save.data.help} />}
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

function useProgress() {
  return useQuery({ queryKey: ["progress"], queryFn: getProgress });
}

function ProgressWidget() {
  const progress = useProgress();
  if (progress.isError) return <ErrorMessage error={progress.error} />;
  const data = progress.data;
  if (!data) return null;
  const span = data.next_level_xp - data.level_start_xp;
  const done = Math.min(span, data.xp - data.level_start_xp);
  return (
    <section
      aria-label="Прогресс"
      data-testid="progress"
      className="space-y-2 rounded-lg border border-slate-300 bg-white p-4"
    >
      <p className="font-semibold">
        <span data-testid="level">Уровень {data.level}</span> ·{" "}
        <span data-testid="streak">Серия: {data.streak} дн.</span>
      </p>
      <progress
        className="w-full"
        max={span}
        value={done}
        aria-label={`Опыт до следующего уровня: ${done} из ${span}`}
      />
      <p className="text-sm text-slate-700" data-testid="xp">
        Опыт: {data.xp} из {data.next_level_xp}
      </p>
    </section>
  );
}

function AchievementsPage() {
  const progress = useProgress();
  const earned = progress.data?.achievements ?? [];
  return (
    <section aria-labelledby="achievements-title" className="space-y-3">
      <h2 id="achievements-title" className="text-xl font-semibold">
        Достижения
      </h2>
      <ErrorMessage error={progress.error} />
      {progress.data && earned.length === 0 && <p>Пока нет достижений.</p>}
      <ul className="space-y-2" data-testid="achievements">
        {earned.map((a) => (
          <li key={a.code} className="rounded border border-slate-300 bg-white p-3">
            <p className="font-semibold">{a.title}</p>
            <p className="text-sm text-slate-700">{a.description}</p>
            <p className="text-sm text-slate-700">
              Получено: <time dateTime={a.earned_on}>{a.earned_on}</time>
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

const TREND_TEXT = {
  up: "настроение растёт",
  down: "настроение снижается",
  flat: "настроение ровное",
  unknown: "мало данных для тренда",
} as const;

function shiftDay(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${String(date.getDate()).padStart(2, "0")}`;
}

function MoodSummary({ start, end }: { start: string; end: string }) {
  const mood = useQuery({ queryKey: ["mood", start, end], queryFn: () => getMood(start, end) });
  if (mood.isError) return <ErrorMessage error={mood.error} />;
  if (!mood.data) return null;
  const { points, average_mood: average, trend } = mood.data;
  return (
    <section aria-labelledby="mood-title" data-testid="mood" className="space-y-2">
      <h3 id="mood-title" className="text-lg font-semibold">
        Динамика настроения
      </h3>
      {points.length === 0 ? (
        <p>За период нет итогов дня.</p>
      ) : (
        <>
          <p>
            Среднее настроение: {average?.toFixed(1)} из 10 — {TREND_TEXT[trend]}.
          </p>
          <ul className="flex flex-wrap gap-2">
            {points.map((point) => (
              <li key={point.date} className="rounded border border-slate-400 px-2 py-1 text-sm">
                {point.date.slice(5)}: {point.mood}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function AnalysisView({ analysis, directions }: { analysis: Analysis; directions: Direction[] }) {
  const direction = directions.find((d) => d.code === analysis.direction)?.title ?? "";
  if (analysis.status === "crisis") {
    return (
      <div className="space-y-3" data-testid="analysis-crisis">
        <p>Сейчас важнее поддержка, чем разбор: паттерны показывать не будем.</p>
        {analysis.help && <HelpPanel help={analysis.help} />}
      </div>
    );
  }
  return (
    <article className="space-y-3" data-testid="analysis-result">
      <h3 className="text-lg font-semibold">
        Разбор ({direction}), {analysis.start} — {analysis.end}
      </h3>
      <p>{analysis.summary}</p>
      {analysis.patterns.length > 0 && (
        <ul className="space-y-2" aria-label="Паттерны">
          {analysis.patterns.map((pattern) => (
            <li key={pattern.title} className="rounded border border-slate-400 p-3">
              <p className="font-semibold">{pattern.title}</p>
              <p>{pattern.description}</p>
              {pattern.quotes.map((quote) => (
                <blockquote key={quote} className="mt-1 border-l-4 border-slate-400 pl-2 text-sm">
                  {quote}
                </blockquote>
              ))}
              <p className="mt-1 text-sm text-slate-700">
                Записи: №{pattern.entry_ids.join(", №")}
              </p>
            </li>
          ))}
        </ul>
      )}
      <QuestIdeas analysis={analysis} />
    </article>
  );
}

function QuestIdeas({ analysis }: { analysis: Analysis }) {
  const client = useQueryClient();
  const take = useMutation({
    mutationFn: (idea: number) => acceptQuestFromAnalysis(analysis.id, idea),
    onSuccess: () => client.invalidateQueries({ queryKey: ["quests"] }),
  });
  if (analysis.quest_ideas.length === 0) return null;
  return (
    <section aria-labelledby={`ideas-${analysis.id}`} className="space-y-2">
      <h4 id={`ideas-${analysis.id}`} className="font-semibold">
        Идеи для квестов
      </h4>
      <ul className="space-y-1">
        {analysis.quest_ideas.map((idea, i) => (
          <li key={idea} className="flex items-center justify-between gap-3">
            <span>{idea}</span>
            <button
              type="button"
              className="text-indigo-800 underline"
              aria-label={`Принять квест: ${idea}`}
              disabled={take.isPending}
              onClick={() => take.mutate(i)}
            >
              Принять квест
            </button>
          </li>
        ))}
      </ul>
      {take.isSuccess && (
        <p role="status">
          Квест принят — он в разделе{" "}
          <Link to="/quests" className="text-indigo-800 underline">
            Квесты
          </Link>
          .
        </p>
      )}
      <ErrorMessage error={take.error} />
    </section>
  );
}

function FollowUp({
  analysis,
  consent,
  onDone,
}: {
  analysis: Analysis;
  consent: boolean;
  onDone: (next: Analysis) => void;
}) {
  const [answers, setAnswers] = useState<string[]>(() => analysis.questions.map(() => ""));
  const send = useMutation({
    mutationFn: () => answerAnalysis(analysis.id, answers, consent),
    onSuccess: onDone,
  });
  if (analysis.status !== "done" || analysis.questions.length === 0) return null;
  return (
    <form
      className="space-y-3"
      aria-label="Уточняющие вопросы"
      onSubmit={(event) => {
        event.preventDefault();
        send.mutate();
      }}
    >
      <h3 className="text-lg font-semibold">Уточняющие вопросы</h3>
      {analysis.questions.map((question, index) => (
        <div key={question}>
          <label htmlFor={`answer-${index}`} className="block">
            {question}
          </label>
          <textarea
            id={`answer-${index}`}
            className={inputClass}
            rows={2}
            value={answers[index] ?? ""}
            onChange={(event) =>
              setAnswers(answers.map((a, i) => (i === index ? event.target.value : a)))
            }
          />
        </div>
      ))}
      <button type="submit" className={buttonClass} disabled={send.isPending || !consent}>
        Уточнить разбор
      </button>
      {!consent && <p className="text-sm">Чтобы отправить ответы, отметьте согласие выше.</p>}
      <ErrorMessage error={send.error} />
    </form>
  );
}

function AnalysisPage() {
  const today = localToday();
  const [start, setStart] = useState(() => shiftDay(today, -6));
  const [end, setEnd] = useState(today);
  const [direction, setDirection] = useState("cbt");
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState<Analysis | null>(null);
  const directions = useQuery({ queryKey: ["directions"], queryFn: listDirections });
  const run = useMutation({
    mutationFn: () => runAnalysis({ direction, start, end, consent }),
    onSuccess: setResult,
  });
  const list = directions.data ?? [];
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Разбор недели</h2>
      <p>
        ИИ посмотрит на ваши обычные записи и итоги дня за период и подскажет паттерны и вопросы для
        размышления. Это не диагноз и не замена специалисту.
      </p>
      <label className="flex items-start gap-2">
        <input
          type="checkbox"
          className="mt-1 h-5 w-5"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
        />
        <span>Согласен(на) передать записи за период ИИ-провайдеру для этого разбора</span>
      </label>
      <details className="rounded border border-slate-400 p-3">
        <summary className="cursor-pointer font-semibold">Период и направление</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="analysis-start">С даты</label>
            <input
              id="analysis-start"
              type="date"
              className={inputClass}
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="analysis-end">По дату</label>
            <input
              id="analysis-end"
              type="date"
              className={inputClass}
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="analysis-direction">Направление</label>
            <select
              id="analysis-direction"
              className={inputClass}
              value={direction}
              onChange={(event) => setDirection(event.target.value)}
            >
              {list.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.title}
                </option>
              ))}
            </select>
          </div>
        </div>
      </details>
      <button
        type="button"
        className={buttonClass}
        data-testid="run-analysis"
        disabled={run.isPending || !consent}
        onClick={() => run.mutate()}
      >
        {run.isPending ? "Разбираю…" : "Разобрать неделю"}
      </button>
      {!consent && <p className="text-sm">Отметьте согласие, чтобы запустить разбор.</p>}
      <ErrorMessage error={run.error} />
      <MoodSummary start={start} end={end} />
      {result && (
        <>
          <AnalysisView analysis={result} directions={list} />
          <FollowUp key={result.id} analysis={result} consent={consent} onDone={setResult} />
        </>
      )}
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
  const [theme, toggleTheme] = useTheme();
  // переключатель откликается сразу (локальное состояние); при ошибке сервера возвращаем прежнее
  const [advanced, setAdvanced] = useState(user.advanced === true);
  const mode = useMutation({
    mutationFn: saveSettings,
    onMutate: (next) => client.setQueryData(["me"], { ...user, advanced: next }),
    onSuccess: (saved) => client.setQueryData(["me"], saved),
    onError: (_error, next) => {
      setAdvanced(!next);
      client.setQueryData(["me"], { ...user, advanced: !next });
    },
  });
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p data-testid="whoami">{user.email}</p>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              data-testid="advanced-toggle"
              checked={advanced}
              onChange={(event) => {
                setAdvanced(event.target.checked);
                mode.mutate(event.target.checked);
              }}
            />
            Advanced
          </label>
          <button
            type="button"
            data-testid="theme-toggle"
            aria-pressed={theme === "dark"}
            className="rounded border border-slate-400 px-3 py-1"
            onClick={toggleTheme}
          >
            Тёмная тема
          </button>
          <button type="button" className="text-indigo-800 underline" onClick={() => out.mutate()}>
            Выйти
          </button>
        </div>
      </div>
      <ErrorMessage error={mode.error} />
      <nav aria-label="Разделы" className="flex flex-wrap gap-4">
        <Link to="/" className="text-indigo-800 underline">
          Дневник
        </Link>
        <Link to="/day" className="text-indigo-800 underline">
          Итог дня
        </Link>
        <Link to="/analysis" className="text-indigo-800 underline">
          Разбор
        </Link>
        <Link to="/quests" className="text-indigo-800 underline">
          Квесты
        </Link>
        <Link to="/achievements" className="text-indigo-800 underline">
          Достижения
        </Link>
      </nav>
      <ProgressWidget />
      {children}
      <p className="border-t border-slate-300 pt-3 text-sm text-slate-700" data-testid="disclaimer">
        Kognis — не медицинская помощь и не заменяет специалиста. В кризисной ситуации звоните 112.
      </p>
    </div>
  );
}

const ONBOARDING_KEY = "kognis-onboarded";

// первый вход: короткое объяснение и дисклеймер; закрытие запоминается в браузере
function Onboarding() {
  const [hidden, setHidden] = useState(() => {
    try {
      return window.localStorage.getItem(ONBOARDING_KEY) === "1";
    } catch {
      return false;
    }
  });
  if (hidden) return null;
  const close = () => {
    try {
      window.localStorage.setItem(ONBOARDING_KEY, "1");
    } catch {
      // без хранилища подсказка вернётся при следующем входе
    }
    setHidden(true);
  };
  return (
    <section
      aria-labelledby="onboarding-title"
      data-testid="onboarding"
      className="space-y-2 rounded-lg border border-amber-700 bg-amber-50 p-4 text-amber-900"
    >
      <h2 id="onboarding-title" className="text-xl font-semibold">
        Добро пожаловать в Kognis
      </h2>
      <p>
        Записывайте мысли и переживания, подводите итог дня, получайте опыт и уровни. Режим Advanced
        (переключатель вверху) открывает графики и фильтры записей.
      </p>
      <p className="font-semibold">
        Kognis не медицинская помощь и не заменяет специалиста. В кризисной ситуации звоните 112.
      </p>
      <button type="button" className={buttonClass} data-testid="onboarding-close" onClick={close}>
        Понятно
      </button>
    </section>
  );
}

function DaySummary() {
  const reviews = useQuery({ queryKey: ["day-reviews"], queryFn: listDayReviews });
  if (reviews.isError) return <ErrorMessage error={reviews.error} />;
  if (!reviews.data) return null;
  const today = reviews.data.find((review) => review.date === localToday());
  return (
    <section
      aria-labelledby="day-summary-title"
      data-testid="day-summary"
      className="space-y-1 rounded-lg border border-slate-300 bg-white p-4"
    >
      <h2 id="day-summary-title" className="text-xl font-semibold">
        Итог дня
      </h2>
      {today ? (
        <p>
          Самочувствие: {today.wellbeing} из 10 · Настроение: {today.mood} из 10
        </p>
      ) : (
        <p>
          Сегодня итог ещё не подведён.{" "}
          <Link to="/day" className="text-indigo-800 underline">
            Заполнить за сегодня
          </Link>
        </p>
      )}
    </section>
  );
}

function HomePage({ advanced }: { advanced: boolean }) {
  return (
    <div className="space-y-6">
      <Onboarding />
      <DaySummary />
      <button
        type="button"
        data-testid="write-cta"
        className="w-full rounded-lg bg-indigo-700 px-6 py-4 text-xl font-bold text-white hover:bg-indigo-800"
        onClick={() => {
          const field = document.getElementById("text");
          field?.scrollIntoView({ block: "center" });
          field?.focus();
        }}
      >
        Записать
      </button>
      <EntryForm />
      {advanced && <MoodChart />}
      <section aria-labelledby="entries-title" className="space-y-3">
        <h2 id="entries-title" className="text-xl font-semibold">
          {advanced ? "Мои записи" : "Последние записи"}
        </h2>
        <EntryList advanced={advanced} />
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
              <HomePage advanced={user.advanced === true} />
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
        <Route
          path="/analysis"
          element={
            <Shell user={user}>
              <AnalysisPage />
            </Shell>
          }
        />
        <Route
          path="/achievements"
          element={
            <Shell user={user}>
              <AchievementsPage />
            </Shell>
          }
        />
        <Route
          path="/quests"
          element={
            <Shell user={user}>
              <QuestsPage />
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
