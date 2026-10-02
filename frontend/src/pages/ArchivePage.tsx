// Мотивация 2.0 (4/4): хранитель архива — «В этот день» (свои записи год/месяц назад, без
// замков) и мозаика настроения за год (Year in Pixels по итогам дня). Только свои данные.
import { useQuery } from "@tanstack/react-query";
import { getMoodYear, getOnThisDay } from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { formatDate, useI18n } from "../i18n";

const MOOD_COLORS = [
  "#b91c1c",
  "#c2410c",
  "#ea580c",
  "#f59e0b",
  "#eab308",
  "#a3e635",
  "#84cc16",
  "#4ade80",
  "#22c55e",
  "#15803d",
] as const;

function moodColor(mood: number): string {
  const idx = Math.min(MOOD_COLORS.length - 1, Math.max(0, mood - 1));
  return MOOD_COLORS[idx] ?? "#15803d";
}

function Ago({ ago }: { ago: string }) {
  const { t } = useI18n();
  return (
    <span className="text-sm muted">
      {ago === "year" ? t("archive.ago.year") : t("archive.ago.month")}
    </span>
  );
}

function OnThisDay() {
  const { t, locale } = useI18n();
  const found = useQuery({ queryKey: ["on-this-day"], queryFn: getOnThisDay, retry: false });
  return (
    <section aria-labelledby="on-this-day-title" className="card space-y-3">
      <h2 id="on-this-day-title" className="text-xl font-semibold">
        {t("archive.on_this_day.title")}
      </h2>
      <ErrorMessage error={found.error} />
      {found.data && found.data.entries.length === 0 && (
        <p className="text-sm muted">{t("archive.on_this_day.empty")}</p>
      )}
      <ul className="space-y-2" data-testid="on-this-day">
        {found.data?.entries.map((entry) => (
          <li key={entry.id} className="card-sm space-y-1">
            <p className="text-sm muted">
              <Ago ago={entry.ago} /> · {formatDate(locale, entry.date)}
            </p>
            <p>{entry.text}</p>
            {entry.tags.length > 0 && <p className="text-sm muted">#{entry.tags.join(" #")}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function MoodMosaic() {
  const { t } = useI18n();
  const year = useQuery({ queryKey: ["mood-year"], queryFn: getMoodYear, retry: false });
  const byDay = new Map(year.data?.days.map((d) => [d.date, d.mood]) ?? []);
  // 365 клеток: с сегодня назад; дни без итога — пустые
  const cells: { date: string; mood: number | null }[] = [];
  const start = new Date();
  for (let offset = 364; offset >= 0; offset--) {
    const day = new Date(start);
    day.setDate(start.getDate() - offset);
    const iso = day.toISOString().slice(0, 10);
    cells.push({ date: iso, mood: byDay.get(iso) ?? null });
  }
  return (
    <section aria-labelledby="mood-year-title" className="card space-y-3">
      <h2 id="mood-year-title" className="text-xl font-semibold">
        {t("archive.mood_year.title")}
      </h2>
      <p className="text-sm muted">{t("archive.mood_year.hint")}</p>
      <ErrorMessage error={year.error} />
      <div
        className="mood-mosaic"
        data-testid="mood-mosaic"
        role="img"
        aria-label={t("archive.mood_year.title")}
      >
        {cells.map((cell) => (
          <span
            key={cell.date}
            className="mood-cell"
            title={cell.date}
            style={
              cell.mood
                ? { backgroundColor: moodColor(cell.mood) }
                : { backgroundColor: "var(--border)" }
            }
          />
        ))}
      </div>
      <p className="text-sm muted" data-testid="mood-year-count">
        {t("archive.mood_year.days", { count: byDay.size })}
      </p>
    </section>
  );
}

export function ArchivePage() {
  const { t } = useI18n();
  return (
    <>
      <h1 className="text-2xl font-semibold">{t("archive.title")}</h1>
      <OnThisDay />
      <MoodMosaic />
    </>
  );
}
