// Графики Advanced-режима: настроение и самочувствие по итогам дня (Recharts).
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getMood } from "../api";
import { shiftDay, useToday } from "../dates";
import { describeError } from "../errors";
import { useI18n } from "../i18n";

const MOOD_COLOR = "#6366f1";
const WELLBEING_COLOR = "#10b981";
const PERIOD_DAYS = 30;

export function MoodChart() {
  const { t, formatDate, formatNumber } = useI18n();
  const end = useToday();
  const start = shiftDay(end, -(PERIOD_DAYS - 1));
  const mood = useQuery({ queryKey: ["mood", start, end], queryFn: () => getMood(start, end) });
  if (mood.isError)
    return (
      <p role="alert">
        {t("chart.load_error")} {describeError(t, mood.error)}
      </p>
    );
  if (!mood.data) return null;
  const { points } = mood.data;
  // подпись оси — день и месяц по правилам языка; дата ISO остаётся ключом
  const data = points.map((p) => ({
    ...p,
    label: formatDate(p.date, { day: "2-digit", month: "2-digit" }),
  }));
  const average = (value: number | null | undefined) =>
    value == null
      ? "—"
      : formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return (
    <section aria-labelledby="mood-chart-title" data-testid="mood-chart" className="space-y-2 card">
      <h2 id="mood-chart-title" className="text-xl font-semibold">
        {t("chart.title", { days: PERIOD_DAYS })}
      </h2>
      {data.length === 0 ? (
        <p className="muted">{t("chart.empty")}</p>
      ) : (
        <>
          <div role="img" aria-label={t("chart.aria", { count: data.length })}>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid stroke="currentColor" strokeOpacity={0.2} />
                <XAxis dataKey="label" stroke="currentColor" tick={{ fill: "currentColor" }} />
                <YAxis
                  domain={[1, 10]}
                  allowDecimals={false}
                  stroke="currentColor"
                  tick={{ fill: "currentColor" }}
                />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="mood"
                  name={t("chart.mood")}
                  stroke={MOOD_COLOR}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="wellbeing"
                  name={t("chart.wellbeing")}
                  stroke={WELLBEING_COLOR}
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-sm muted">
            {t("chart.average", {
              mood: average(mood.data.average_mood),
              wellbeing: average(mood.data.average_wellbeing),
            })}
          </p>
        </>
      )}
    </section>
  );
}
