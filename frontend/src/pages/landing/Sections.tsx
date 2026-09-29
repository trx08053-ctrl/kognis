// Секции лендинга ниже первого экрана.
import { type KeyboardEvent, type ReactNode, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BookIcon, FlagIcon, HeartIcon, ShieldIcon, SparkIcon, SunIcon } from "../../Icons";
import {
  DEMO_EMOTIONS,
  DEMO_ENTRY,
  DEMO_LENSES,
  FEATURES,
  type FeatureKey,
  METRICS,
  type Metric,
  RESEARCH,
  STATS,
  STEPS,
  TREND,
} from "./content";
import { CountUp, Reveal } from "./motion";

const FEATURE_ICONS: Record<FeatureKey, () => ReactNode> = {
  diary: BookIcon,
  analysis: SparkIcon,
  day: SunIcon,
  quests: FlagIcon,
  privacy: ShieldIcon,
  safety: HeartIcon,
};

// КПТ-разбор — шире, безопасность — плашкой на всю строку: сетка 3 колонки без «сирот»
const BENTO_CLASS: Partial<Record<FeatureKey, string>> = {
  analysis: "lp-bento-wide",
  safety: "lp-bento-full",
};

export function SectionHead({
  id,
  eyebrow,
  title,
  text,
}: {
  id: string;
  eyebrow: string;
  title: string;
  text?: string;
}) {
  return (
    <Reveal className="mx-auto mb-10 max-w-2xl text-center">
      <p className="lp-eyebrow">{eyebrow}</p>
      <h2 id={id} className="lp-h2">
        {title}
      </h2>
      {text && <p className="mt-4 text-lg muted">{text}</p>}
    </Reveal>
  );
}

export function Stats() {
  return (
    <section aria-label="Kognis в цифрах" className="lp-container">
      <ul className="lp-stats">
        {STATS.map((s, i) => (
          <li key={s.label}>
            <Reveal delay={(i % 4) as 0 | 1 | 2 | 3}>
              <p className="lp-stat-value">
                <CountUp value={s.value} suffix={s.suffix} />
              </p>
              <p className="text-sm muted">{s.label}</p>
            </Reveal>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Features() {
  return (
    <section aria-labelledby="features-title" id="features" className="lp-section lp-container">
      <SectionHead
        id="features-title"
        eyebrow="Возможности"
        title="Всё, чтобы лучше понимать себя"
        text="Kognis соединяет дневник, психологические подходы и игровую механику — чтобы забота о себе была простой и регулярной."
      />
      <ul className="lp-bento">
        {FEATURES.map((f, i) => {
          const Icon = FEATURE_ICONS[f.key];
          return (
            <li key={f.key} className={BENTO_CLASS[f.key] ?? ""}>
              <Reveal delay={(i % 3) as 0 | 1 | 2} className="lp-card lp-feature h-full">
                <span className="lp-icon">
                  <Icon />
                </span>
                <h3 className="mt-4 text-xl font-semibold">{f.title}</h3>
                <p className="mt-2 muted">{f.text}</p>
                {f.key === "analysis" && (
                  <p className="mt-4 flex flex-wrap gap-2">
                    {DEMO_LENSES.map((l) => (
                      <span key={l.code} className="badge">
                        {l.title}
                      </span>
                    ))}
                  </p>
                )}
              </Reveal>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" id="how" className="lp-section lp-container">
      <SectionHead
        id="how-title"
        eyebrow="Как это работает"
        title="Три шага от переживания к ясности"
      />
      <ol className="lp-steps">
        {STEPS.map((s, i) => (
          <li key={s.title}>
            <Reveal delay={i as 0 | 1 | 2} className="lp-card h-full">
              <span className="lp-step-num" aria-hidden="true">
                {i + 1}
              </span>
              <h3 className="mt-4 text-xl font-semibold">{s.title}</h3>
              <p className="mt-2 muted">{s.text}</p>
            </Reveal>
          </li>
        ))}
      </ol>
      <Demo />
    </section>
  );
}

export function Demo() {
  const [active, setActive] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const lens = DEMO_LENSES[active] ?? DEMO_LENSES[0];

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, number> = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1,
    };
    let next: number | null = null;
    if (event.key in moves)
      next = (active + (moves[event.key] ?? 0) + DEMO_LENSES.length) % DEMO_LENSES.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = DEMO_LENSES.length - 1;
    if (next === null) return;
    event.preventDefault();
    setActive(next);
    tabs.current[next]?.focus();
  }

  if (!lens) return null;
  return (
    <Reveal className="lp-demo mt-12">
      <div className="lp-demo-entry">
        <p className="lp-eyebrow">Попробуйте: одна запись — пять взглядов</p>
        <h3 className="mt-2 text-2xl font-semibold">Запись в дневнике</h3>
        <blockquote className="lp-entry-quote">{DEMO_ENTRY}</blockquote>
        <p className="mt-3 flex flex-wrap gap-2">
          {DEMO_EMOTIONS.map((e) => (
            <span key={e} className="chip chip-on">
              {e}
            </span>
          ))}
        </p>
      </div>
      <div className="lp-demo-result">
        <div role="tablist" aria-label="Направление разбора" className="lp-tabs" onKeyDown={onKey}>
          {DEMO_LENSES.map((l, i) => (
            <button
              key={l.code}
              ref={(el) => {
                tabs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`lens-tab-${l.code}`}
              aria-selected={i === active}
              aria-controls="lens-panel"
              tabIndex={i === active ? 0 : -1}
              className="lp-tab"
              onClick={() => setActive(i)}
            >
              {l.title}
            </button>
          ))}
        </div>
        <div
          role="tabpanel"
          id="lens-panel"
          aria-labelledby={`lens-tab-${lens.code}`}
          className="lp-lens"
          data-testid="demo-lens"
          key={lens.code}
        >
          <dl className="space-y-4">
            <div>
              <dt className="lp-eyebrow">Паттерн</dt>
              <dd className="mt-1">{lens.pattern}</dd>
            </div>
            <div>
              <dt className="lp-eyebrow">Вопрос для размышления</dt>
              <dd className="mt-1">{lens.question}</dd>
            </div>
            <div>
              <dt className="lp-eyebrow">Маленький шаг</dt>
              <dd className="mt-1">{lens.step}</dd>
            </div>
          </dl>
        </div>
        <p className="mt-3 text-sm muted">
          Пример разбора. В приложении он строится по вашим записям.
        </p>
      </div>
    </Reveal>
  );
}

const METRIC_COLORS: Record<Metric, string> = {
  mood: "#6366f1",
  wellbeing: "#0d9488",
};

export function Results() {
  const [metric, setMetric] = useState<Metric>("mood");
  const current = METRICS.find((m) => m.key === metric);
  const color = METRIC_COLORS[metric];
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  if (!current) return null;
  return (
    <section aria-labelledby="results-title" id="results" className="lp-section lp-container">
      <SectionHead
        id="results-title"
        eyebrow="Результаты"
        title="Изменения, которые видно на графике"
        text="Регулярные записи и итоги дня складываются в динамику: вы видите, что помогает, а что забирает силы."
      />
      <div className="lp-results">
        <Reveal className="lp-card">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-semibold">8 недель с Kognis</h3>
              <p className="text-sm muted">{current.hint}</p>
            </div>
            <fieldset className="lp-toggle">
              <legend className="sr-only">Показатель на графике</legend>
              {METRICS.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  aria-pressed={m.key === metric}
                  onClick={() => setMetric(m.key)}
                >
                  {m.label}
                </button>
              ))}
            </fieldset>
          </div>
          <p className="mt-4 text-3xl font-bold" data-testid="metric-delta">
            {current.better}
          </p>
          <div
            role="img"
            aria-label={`График «${current.label}» за 8 недель: ${TREND.map((t) => t[metric]).join(", ")}`}
            className="mt-2"
          >
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={[...TREND]} margin={{ top: 10, right: 8, bottom: 0, left: -24 }}>
                <defs>
                  <linearGradient id="lp-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="currentColor" strokeOpacity={0.12} vertical={false} />
                <XAxis
                  dataKey="week"
                  stroke="currentColor"
                  tick={{ fill: "currentColor", fontSize: 12 }}
                />
                <YAxis
                  domain={[1, 10]}
                  stroke="currentColor"
                  tick={{ fill: "currentColor", fontSize: 12 }}
                />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey={metric}
                  name={current.label}
                  stroke={color}
                  strokeWidth={3}
                  fill="url(#lp-fill)"
                  isAnimationActive={!reduced}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs muted">
            Иллюстрация: так может выглядеть ваша динамика в разделе «Итог дня». Реальные графики
            строятся по вашим записям; результат у каждого свой.
          </p>
        </Reveal>
        <ul className="space-y-4">
          {RESEARCH.map((r, i) => (
            <li key={r.title}>
              <Reveal delay={i as 0 | 1 | 2} className="lp-card lp-research">
                <h3 className="font-semibold">{r.title}</h3>
                <p className="mt-1 muted">{r.text}</p>
                <p className="mt-2 text-xs muted">{r.source}</p>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
