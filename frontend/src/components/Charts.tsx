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

const MOOD_COLOR = "#6366f1";
const WELLBEING_COLOR = "#10b981";
const PERIOD_DAYS = 30;

export function MoodChart() {
  const end = useToday();
  const start = shiftDay(end, -(PERIOD_DAYS - 1));
  const mood = useQuery({ queryKey: ["mood", start, end], queryFn: () => getMood(start, end) });
  if (mood.isError) return <p role="alert">Не удалось загрузить график: {mood.error.message}</p>;
  if (!mood.data) return null;
  const { points } = mood.data;
  // «дд.мм» по-русски; дата ISO остаётся ключом
  const data = points.map((p) => ({ ...p, label: `${p.date.slice(8)}.${p.date.slice(5, 7)}` }));
  return (
    <section aria-labelledby="mood-chart-title" data-testid="mood-chart" className="space-y-2 card">
      <h2 id="mood-chart-title" className="text-xl font-semibold">
        Настроение и самочувствие за {PERIOD_DAYS} дней
      </h2>
      {data.length === 0 ? (
        <p className="muted">Пока нет итогов дня — график появится после первого.</p>
      ) : (
        <>
          <div role="img" aria-label={`График: ${data.length} итогов дня, шкала от 1 до 10`}>
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
                  name="Настроение"
                  stroke={MOOD_COLOR}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="wellbeing"
                  name="Самочувствие"
                  stroke={WELLBEING_COLOR}
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-sm muted">
            Среднее настроение: {mood.data.average_mood?.toFixed(1) ?? "—"} · самочувствие:{" "}
            {mood.data.average_wellbeing?.toFixed(1) ?? "—"} (из 10).
          </p>
        </>
      )}
    </section>
  );
}
