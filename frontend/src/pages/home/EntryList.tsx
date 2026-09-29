import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { type Entry, getEntryLabels, listEntries } from "../../api";
import { ErrorMessage } from "../../components/ErrorMessage";
import { LockedEntryBody, PrivateEntryBody } from "./EntryBodies";

const inputClass = "input";

interface EntryFilters {
  tag: string;
  emotion: string;
  from: string;
  to: string;
}

const NO_FILTERS: EntryFilters = { tag: "", emotion: "", from: "", to: "" };

const PAGE_SIZE = 30;

function EntryFilterBar({
  filters,
  onChange,
}: {
  filters: EntryFilters;
  onChange: (next: EntryFilters) => void;
}) {
  // варианты фильтров — все теги и эмоции пользователя, а не только загруженные страницы
  const labels = useQuery({ queryKey: ["entries", "labels"], queryFn: getEntryLabels });
  const tags = labels.data?.tags ?? [];
  const emotions = labels.data?.emotions ?? [];
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

// простой режим — последние записи; Advanced — все записи страницами с фильтрами на сервере
export function EntryList({ advanced }: { advanced: boolean }) {
  return advanced ? <AllEntries /> : <RecentEntries />;
}

function RecentEntries() {
  const entries = useQuery({
    queryKey: ["entries", "recent"],
    queryFn: () => listEntries({ limit: RECENT_LIMIT }),
  });
  if (entries.isError) return <ErrorMessage error={entries.error} />;
  const items = entries.data?.items ?? [];
  if (items.length === 0) return <p className="muted">Пока нет записей.</p>;
  return <EntryItems items={items.slice(0, RECENT_LIMIT)} />;
}

function AllEntries() {
  const [filters, setFilters] = useState<EntryFilters>(NO_FILTERS);
  const filtered = Object.values(filters).some((value) => value !== "");
  const entries = useInfiniteQuery({
    queryKey: ["entries", "list", filters],
    queryFn: ({ pageParam }) =>
      listEntries({
        limit: PAGE_SIZE,
        cursor: pageParam,
        tag: filters.tag,
        emotion: filters.emotion,
        from: filters.from,
        to: filters.to,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next,
    placeholderData: keepPreviousData,
  });
  if (entries.isError) return <ErrorMessage error={entries.error} />;
  const items: Entry[] = entries.data?.pages.flatMap((page) => page.items) ?? [];
  if (items.length === 0 && !filtered) {
    return entries.isPending ? null : <p className="muted">Пока нет записей.</p>;
  }
  return (
    <>
      <EntryFilterBar filters={filters} onChange={(next) => setFilters(next)} />
      {items.length === 0 ? (
        <p className="muted">По фильтрам ничего не найдено.</p>
      ) : (
        <EntryItems items={items} />
      )}
      {entries.hasNextPage && (
        <button
          type="button"
          className="btn"
          data-testid="more-entries"
          disabled={entries.isFetchingNextPage}
          onClick={() => void entries.fetchNextPage()}
        >
          Показать ещё
        </button>
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
