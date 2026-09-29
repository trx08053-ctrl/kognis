import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes } from "react-router";
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
import { browserTimeZone, shiftDay, timeZoneNames, useToday } from "./dates";
import {
  BookIcon,
  FlagIcon,
  FlameIcon,
  LogoutIcon,
  MoonIcon,
  PencilIcon,
  SparkIcon,
  SunIcon,
  TrophyIcon,
  UserIcon,
} from "./Icons";
import { decryptText, encryptText, MIN_PRIVATE_PASSWORD } from "./privateCrypto";
import { QuestsPage } from "./Quests";
import { useTheme } from "./theme";

const inputClass = "input";
const buttonClass = "btn";

function splitList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item !== "");
}

function ErrorMessage({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <p className="mt-2 font-semibold text-[var(--danger-text)]" role="alert">
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
    mutationFn: async () => {
      if (mode === "login") return login(email, password);
      const zone = browserTimeZone();
      try {
        return await register(email, password, zone);
      } catch (error) {
        // браузерное имя пояса, которого нет в tzdata сервера, не должно ломать регистрацию:
        // повторяем без него (сервер возьмёт пояс по умолчанию), пояс можно сменить в профиле
        if (zone !== null && error instanceof ApiError && error.status === 422) {
          return register(email, password, null);
        }
        throw error;
      }
    },
    onSuccess: (user) => client.setQueryData(["me"], user),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    auth.mutate();
  }

  return (
    <form className="space-y-4 card" onSubmit={submit}>
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
          className="link"
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
      className="rounded-2xl border-2 border-[var(--danger-border)] bg-[var(--danger-bg)] p-4 text-[var(--danger-text)]"
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

const EMOTION_DICTIONARY = [
  "радость",
  "спокойствие",
  "благодарность",
  "интерес",
  "надежда",
  "усталость",
  "тревога",
  "грусть",
  "злость",
  "стыд",
  "одиночество",
  "растерянность",
];

type Protection = "plain" | "locked" | "private";

const PROTECTION_HINT: Record<Protection, string> = {
  plain: "Текст хранится на сервере и доступен ИИ-разбору, если вы дали согласие.",
  locked: "Текст закрыт паролем: без пароля его не увидит никто, ИИ его не читает.",
  private: "Текст шифруется на этом устройстве: сервер и ИИ его не прочитают.",
};

const PROTECTION_LABEL: Record<Protection, string> = {
  plain: "Обычная",
  locked: "Под замком",
  private: "Приватная",
};

// список чипов: выбор из словаря/своих значений, кнопка-чип переключает выбор
function ChipToggleGroup({
  legend,
  options,
  selected,
  onToggle,
}: {
  legend: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-1 font-semibold">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className="chip"
            aria-pressed={selected.includes(option)}
            onClick={() => onToggle(option)}
          >
            {option}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

// поле «добавить своё»: значения через запятую или Enter становятся чипами; недописанное
// значение попадает в запись при сохранении
function CustomChipInput({
  id,
  label,
  chips,
  pending,
  onPending,
  onCommit,
  onRemove,
  removeLabel,
}: {
  id: string;
  label: string;
  chips: string[];
  pending: string;
  onPending: (value: string) => void;
  onCommit: (values: string[]) => void;
  onRemove: (value: string) => void;
  removeLabel: string;
}) {
  const commit = (raw: string) => {
    onCommit(splitList(raw));
    onPending("");
  };
  return (
    <div>
      <label htmlFor={id} className="mb-1 block font-semibold">
        {label}
      </label>
      {chips.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-2">
          {chips.map((chip) => (
            <li key={chip}>
              <button
                type="button"
                className="chip chip-on"
                aria-label={`${removeLabel}: ${chip}`}
                onClick={() => onRemove(chip)}
              >
                {chip} <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        id={id}
        className={inputClass}
        value={pending}
        onChange={(event) => {
          const value = event.target.value;
          if (value.includes(",")) commit(value);
          else onPending(value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && pending.trim() !== "") {
            event.preventDefault();
            commit(pending);
          }
        }}
        onBlur={() => pending.trim() !== "" && commit(pending)}
      />
    </div>
  );
}

function addUnique(list: string[], values: string[]): string[] {
  return [...list, ...values.filter((value) => !list.includes(value))];
}

function EntryForm() {
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [pendingTag, setPendingTag] = useState("");
  const [emotions, setEmotions] = useState<string[]>([]);
  const [pendingEmotion, setPendingEmotion] = useState("");
  const [protection, setProtection] = useState<Protection>("plain");
  const [lockPassword, setLockPassword] = useState("");
  const [privatePassword, setPrivatePassword] = useState("");
  const [privateRepeat, setPrivateRepeat] = useState("");
  const locked = protection === "locked";
  const isPrivate = protection === "private";
  const add = useMutation({
    mutationFn: async () => {
      const labels = {
        tags: addUnique(tags, splitList(pendingTag)),
        emotions: addUnique(emotions, splitList(pendingEmotion)),
      };
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
      setTags([]);
      setPendingTag("");
      setEmotions([]);
      setPendingEmotion("");
      setProtection("plain");
      setLockPassword("");
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
    <form className="space-y-4 card" onSubmit={submit}>
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
      <ChipToggleGroup
        legend="Как вы себя чувствуете"
        options={addUnique(EMOTION_DICTIONARY, emotions)}
        selected={emotions}
        onToggle={(value) =>
          setEmotions(
            emotions.includes(value) ? emotions.filter((e) => e !== value) : [...emotions, value],
          )
        }
      />
      <CustomChipInput
        id="emotions"
        label="Своя эмоция"
        chips={[]}
        pending={pendingEmotion}
        onPending={setPendingEmotion}
        onCommit={(values) => setEmotions(addUnique(emotions, values))}
        onRemove={() => undefined}
        removeLabel="Убрать эмоцию"
      />
      <CustomChipInput
        id="tags"
        label="Теги"
        chips={tags}
        pending={pendingTag}
        onPending={setPendingTag}
        onCommit={(values) => setTags(addUnique(tags, values))}
        onRemove={(value) => setTags(tags.filter((t) => t !== value))}
        removeLabel="Убрать тег"
      />
      <fieldset className="space-y-2">
        <legend className="mb-1 font-semibold">Защита записи</legend>
        <div className="segmented" role="radiogroup" aria-label="Режим защиты">
          {(Object.keys(PROTECTION_LABEL) as Protection[]).map((value) => (
            <label key={value}>
              <input
                type="radio"
                name="protection"
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                checked={protection === value}
                onChange={() => setProtection(value)}
              />
              {PROTECTION_LABEL[value]}
            </label>
          ))}
        </div>
        <p className="text-sm muted">{PROTECTION_HINT[protection]}</p>
        {isPrivate && (
          <div className="mt-2 space-y-2">
            <p className="notice" data-testid="private-warning">
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
      </fieldset>
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
        <button type="button" className="mt-2 link" onClick={() => setOpened(null)}>
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
        <button type="button" className="mt-2 link" onClick={() => setOpened(null)}>
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
      className="grid gap-3 card sm:grid-cols-2"
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
  if (all.length === 0) return <p className="muted">Пока нет записей.</p>;
  const items = advanced
    ? all.filter((entry) => matchesFilters(entry, filters))
    : all.slice(0, RECENT_LIMIT);
  return (
    <>
      {advanced && <EntryFilterBar entries={all} filters={filters} onChange={setFilters} />}
      {items.length === 0 ? (
        <p className="muted">По фильтрам ничего не найдено.</p>
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
        <li key={entry.id} className="card">
          <p className="text-sm muted">{entry.date}</p>
          {entry.protection === "locked" && <LockedEntryBody entry={entry} />}
          {entry.protection === "private" && <PrivateEntryBody entry={entry} />}
          {entry.protection !== "locked" && entry.protection !== "private" && (
            <p className="whitespace-pre-wrap">{entry.text}</p>
          )}
          {(entry.tags.length > 0 || entry.emotions.length > 0) && (
            <p className="mt-2 flex flex-wrap gap-2 text-sm">
              {entry.emotions.map((emotion) => (
                <span key={`e-${emotion}`} className="badge">
                  {emotion}
                </span>
              ))}
              {entry.tags.map((tag) => (
                <span key={`t-${tag}`} className="muted">
                  #{tag}
                </span>
              ))}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
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
        <output htmlFor={id} className="text-2xl text-[var(--accent-text)]">
          {value}
        </output>
      </label>
      <input
        id={id}
        type="range"
        min={1}
        max={10}
        step={1}
        className="w-full accent-[var(--accent)]"
        aria-describedby={`${id}-hint`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <div id={`${id}-hint`} className="flex justify-between text-sm muted">
        <span>1 · {low}</span>
        <span>{high} · 10</span>
      </div>
    </div>
  );
}

function DayReviewForm() {
  const client = useQueryClient();
  const today = useToday();
  const [date, setDate] = useState(today);
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
    <form className="space-y-4 card" onSubmit={submit} noValidate>
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
        <p className="mt-2 font-semibold text-[var(--ok-text)]" role="status">
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
  if (items.length === 0) return <p className="muted">Пока нет итогов дня.</p>;
  return (
    <ul className="space-y-3" data-testid="reviews">
      {items.map((review) => (
        <li key={review.id} className="card">
          <p className="text-sm muted">{review.date}</p>
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
    <section aria-label="Прогресс" data-testid="progress" className="space-y-2 card">
      <div
        className="meter"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={span}
        aria-valuenow={done}
        aria-label={`Опыт до следующего уровня: ${done} из ${span}`}
      >
        <div style={{ width: `${span > 0 ? (done / span) * 100 : 0}%` }} />
      </div>
      <p className="text-sm muted" data-testid="xp">
        Опыт: {data.xp} из {data.next_level_xp}
      </p>
    </section>
  );
}

function Achievements() {
  const progress = useProgress();
  const earned = progress.data?.achievements ?? [];
  return (
    <section aria-labelledby="achievements-title" className="space-y-3">
      <h3 id="achievements-title" className="text-lg font-semibold">
        Достижения
      </h3>
      <ErrorMessage error={progress.error} />
      {progress.data && earned.length === 0 && <p>Пока нет достижений.</p>}
      <ul className="space-y-2" data-testid="achievements">
        {earned.map((a) => (
          <li key={a.code} className="card-sm flex items-start gap-3">
            <span className="badge !p-2" aria-hidden="true">
              <TrophyIcon />
            </span>
            <div>
              <p className="font-semibold">{a.title}</p>
              <p className="text-sm muted">{a.description}</p>
              <p className="text-sm muted">
                Получено: <time dateTime={a.earned_on}>{a.earned_on}</time>
              </p>
            </div>
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
              <li key={point.date} className="badge">
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
            <li key={pattern.title} className="card-sm">
              <p className="font-semibold">{pattern.title}</p>
              <p>{pattern.description}</p>
              {pattern.quotes.map((quote) => (
                <blockquote
                  key={quote}
                  className="mt-1 border-l-4 border-[var(--accent)] pl-2 text-sm"
                >
                  {quote}
                </blockquote>
              ))}
              <p className="mt-1 text-sm muted">Записи: №{pattern.entry_ids.join(", №")}</p>
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
              className="link"
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
          <Link to="/quests" className="link">
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
  const today = useToday();
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
      <details className="card-sm">
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

// смена часового пояса профиля: по нему сервер и интерфейс считают «сегодня»
function TimezoneField({ user }: { user: User }) {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: (timezone: string) => saveSettings({ timezone }),
    onSuccess: (saved) => {
      client.setQueryData(["me"], saved);
      return client.invalidateQueries({ queryKey: ["progress"] });
    },
  });
  const zones = timeZoneNames(user.timezone);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="timezone" className="font-semibold">
        Часовой пояс
      </label>
      <select
        id="timezone"
        data-testid="timezone-select"
        className={`${inputClass} !w-auto max-w-full`}
        value={user.timezone}
        onChange={(event) => save.mutate(event.target.value)}
      >
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone}
          </option>
        ))}
      </select>
      <ErrorMessage error={save.error} />
    </div>
  );
}

// профиль: настройки (режим Advanced, часовой пояс) и достижения
function ProfilePage({ user }: { user: User }) {
  const client = useQueryClient();
  // переключатель откликается сразу (локальное состояние); при ошибке сервера возвращаем прежнее
  const [advanced, setAdvanced] = useState(user.advanced === true);
  const mode = useMutation({
    mutationFn: (next: boolean) => saveSettings({ advanced: next }),
    onMutate: (next) => client.setQueryData(["me"], { ...user, advanced: next }),
    onSuccess: (saved) => client.setQueryData(["me"], saved),
    onError: (_error, next) => {
      setAdvanced(!next);
      client.setQueryData(["me"], { ...user, advanced: !next });
    },
  });
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Профиль</h2>
      <section aria-labelledby="settings-title" className="card space-y-3">
        <h3 id="settings-title" className="text-lg font-semibold">
          Настройки
        </h3>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="h-5 w-5 accent-[var(--accent)]"
            data-testid="advanced-toggle"
            checked={advanced}
            onChange={(event) => {
              setAdvanced(event.target.checked);
              mode.mutate(event.target.checked);
            }}
          />
          Advanced
        </label>
        <p className="text-sm muted">Графики настроения и фильтры записей на странице «Дневник».</p>
        <ErrorMessage error={mode.error} />
        <TimezoneField user={user} />
      </section>
      <Achievements />
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
  const progress = useProgress();
  return (
    <div className="space-y-6">
      <header className="card flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-lg font-bold text-[var(--accent-fg)]"
          >
            {user.email.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p data-testid="whoami" className="min-w-0 truncate font-semibold">
              {user.email}
            </p>
            {progress.data && (
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                <span className="badge" data-testid="level">
                  Уровень {progress.data.level}
                </span>
                <span className="badge">
                  <FlameIcon />
                  <span data-testid="streak">Серия: {progress.data.streak} дн.</span>
                </span>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="theme-toggle"
            className="btn-ghost"
            onClick={toggleTheme}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
          </button>
          <button type="button" className="btn-ghost" onClick={() => out.mutate()}>
            <LogoutIcon />
            Выйти
          </button>
        </div>
      </header>
      <ProgressWidget />
      <nav aria-label="Разделы" className="nav m-0">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} end className="nav-link">
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>
      {children}
      <p className="border-t border-[var(--border)] pt-3 text-sm muted" data-testid="disclaimer">
        Kognis — не медицинская помощь и не заменяет специалиста. В кризисной ситуации звоните 112.
      </p>
    </div>
  );
}

const NAV = [
  { to: "/", label: "Дневник", Icon: BookIcon },
  { to: "/day", label: "Итог дня", Icon: SunIcon },
  { to: "/analysis", label: "Разбор", Icon: SparkIcon },
  { to: "/quests", label: "Квесты", Icon: FlagIcon },
  { to: "/profile", label: "Профиль", Icon: UserIcon },
];

const ONBOARDING_KEY = "kognis-onboarded";

// первый вход: короткое объяснение (дисклеймер — в подвале); закрытие запоминается в браузере
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
      className="notice space-y-2"
    >
      <h2 id="onboarding-title" className="text-xl font-semibold">
        Добро пожаловать в Kognis
      </h2>
      <p>
        Записывайте мысли и переживания, подводите итог дня, получайте опыт и уровни. Режим Advanced
        (в разделе «Профиль») открывает графики и фильтры записей.
      </p>
      <button type="button" className={buttonClass} data-testid="onboarding-close" onClick={close}>
        Понятно
      </button>
    </section>
  );
}

function DaySummary() {
  const todayDate = useToday();
  const reviews = useQuery({ queryKey: ["day-reviews"], queryFn: listDayReviews });
  if (reviews.isError) return <ErrorMessage error={reviews.error} />;
  if (!reviews.data) return null;
  const today = reviews.data.find((review) => review.date === todayDate);
  return (
    <section
      aria-labelledby="day-summary-title"
      data-testid="day-summary"
      className="space-y-1 card"
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
          <Link to="/day" className="link">
            Заполнить за сегодня
          </Link>
        </p>
      )}
    </section>
  );
}

export function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return "Доброе утро";
  if (hour >= 12 && hour < 18) return "Добрый день";
  if (hour >= 18 && hour < 23) return "Добрый вечер";
  return "Доброй ночи";
}

function HomePage({ advanced }: { advanced: boolean }) {
  return (
    <div className="space-y-6">
      <Onboarding />
      <h2 className="text-2xl font-bold" data-testid="greeting">
        {greeting(new Date().getHours())}
      </h2>
      <DaySummary />
      <button
        type="button"
        data-testid="write-cta"
        className="btn flex w-full items-center justify-center gap-2 !py-4 text-xl"
        onClick={() => {
          const field = document.getElementById("text");
          field?.scrollIntoView({ block: "center" });
          field?.focus();
        }}
      >
        <PencilIcon />
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
          path="/profile"
          element={
            <Shell user={user}>
              <ProfilePage user={user} />
            </Shell>
          }
        />
        <Route path="/achievements" element={<Navigate to="/profile" replace />} />
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
    <div className={user ? "layout" : ""}>
      <main className="mx-auto max-w-2xl space-y-6 px-4 pb-28 pt-6 md:pb-10">
        <h1 className="text-3xl font-bold">Kognis</h1>
        <p className="text-sm muted">Дневник переживаний.</p>
        {body}
      </main>
    </div>
  );
}
