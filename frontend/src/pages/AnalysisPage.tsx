import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import {
  type Analysis,
  acceptQuestFromAnalysis,
  answerAnalysis,
  type Direction,
  deleteAnalysis,
  getMood,
  listAnalyses,
  listDirections,
  runAnalysis,
} from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { HelpPanel } from "../components/HelpPanel";
import { shiftDay, useToday } from "../dates";
import { useI18n } from "../i18n";

const inputClass = "input";
const buttonClass = "btn";

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
  const { t } = useI18n();
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
      {analysis.answers.length > 0 && (
        <section aria-labelledby={`answers-${analysis.id}`} className="space-y-1">
          <h4 id={`answers-${analysis.id}`} className="font-semibold">
            {t("analysis.answers.title")}
          </h4>
          <ul className="list-disc ps-5">
            {analysis.answers.map((answer) => (
              <li key={answer}>{answer}</li>
            ))}
          </ul>
        </section>
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

function HistoryItem({
  analysis,
  directions,
  current,
  onOpen,
  onDeleted,
}: {
  analysis: Analysis;
  directions: Direction[];
  current: boolean;
  onOpen: () => void;
  onDeleted: () => void;
}) {
  const { t, formatDate } = useI18n();
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const remove = useMutation({
    mutationFn: () => deleteAnalysis(analysis.id),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["analyses"] });
      onDeleted();
    },
  });
  const created = analysis.created_at ? formatDate(analysis.created_at) : `№${analysis.id}`;
  const label = t("analysis.history.item", {
    created,
    start: formatDate(analysis.start),
    end: formatDate(analysis.end),
    direction: directions.find((d) => d.code === analysis.direction)?.title ?? analysis.direction,
    status: t(analysis.status === "crisis" ? "analysis.status.crisis" : "analysis.status.done"),
  });
  return (
    <li className="card-sm space-y-2" data-testid="analysis-history-item">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          className="link text-start"
          aria-current={current ? "true" : undefined}
          aria-label={t("analysis.history.open", { created })}
          onClick={onOpen}
        >
          {label}
        </button>
        {confirming ? (
          <span className="flex items-center gap-2">
            <span>{t("analysis.history.delete_confirm")}</span>
            <button
              type="button"
              className="link"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t("analysis.history.delete_yes")}
            </button>
            <button type="button" className="link" onClick={() => setConfirming(false)}>
              {t("analysis.history.delete_no")}
            </button>
          </span>
        ) : (
          <button
            type="button"
            className="link"
            aria-label={t("analysis.history.delete_aria", { created })}
            onClick={() => setConfirming(true)}
          >
            {t("analysis.history.delete")}
          </button>
        )}
      </div>
      <ErrorMessage error={remove.error} />
    </li>
  );
}

function AnalysisHistory({
  items,
  directions,
  currentId,
  hasMore,
  loadingMore,
  onMore,
  onOpen,
  onDeleted,
}: {
  items: Analysis[];
  directions: Direction[];
  currentId: number | null;
  hasMore: boolean;
  loadingMore: boolean;
  onMore: () => void;
  onOpen: (analysis: Analysis) => void;
  onDeleted: (analysis: Analysis) => void;
}) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="analysis-history-title" className="space-y-3">
      <h3 id="analysis-history-title" className="text-lg font-semibold">
        {t("analysis.history.title")}
      </h3>
      {items.length === 0 ? (
        <p className="muted">{t("analysis.history.empty")}</p>
      ) : (
        <ul className="space-y-2" data-testid="analysis-history">
          {items.map((analysis) => (
            <HistoryItem
              key={analysis.id}
              analysis={analysis}
              directions={directions}
              current={analysis.id === currentId}
              onOpen={() => onOpen(analysis)}
              onDeleted={() => onDeleted(analysis)}
            />
          ))}
        </ul>
      )}
      {hasMore && (
        <button
          type="button"
          className={buttonClass}
          data-testid="more-analyses"
          disabled={loadingMore}
          onClick={onMore}
        >
          {t("analysis.history.more")}
        </button>
      )}
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

export function AnalysisPage() {
  const today = useToday();
  const [start, setStart] = useState(() => shiftDay(today, -6));
  const [end, setEnd] = useState(today);
  const [direction, setDirection] = useState("cbt");
  const [consent, setConsent] = useState(false);
  const client = useQueryClient();
  // явно выбранный разбор (новый или открытый из истории); пока не выбран — последний из истории
  const [chosen, setChosen] = useState<Analysis | null>(null);
  const directions = useQuery({ queryKey: ["directions"], queryFn: listDirections });
  const history = useInfiniteQuery({
    queryKey: ["analyses"],
    queryFn: ({ pageParam }) => listAnalyses(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next,
  });
  const items = history.data?.pages.flatMap((page) => page.items) ?? [];
  const result = chosen ?? items[0] ?? null;
  const show = (analysis: Analysis) => {
    setChosen(analysis);
    void client.invalidateQueries({ queryKey: ["analyses"] });
  };
  const run = useMutation({
    mutationFn: () => runAnalysis({ direction, start, end, consent }),
    onSuccess: show,
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
          <FollowUp key={result.id} analysis={result} consent={consent} onDone={show} />
        </>
      )}
      {history.isError ? (
        <ErrorMessage error={history.error} />
      ) : (
        <AnalysisHistory
          items={items}
          directions={list}
          currentId={result?.id ?? null}
          hasMore={history.hasNextPage}
          loadingMore={history.isFetchingNextPage}
          onMore={() => void history.fetchNextPage()}
          onOpen={setChosen}
          onDeleted={(gone) => {
            if (result?.id === gone.id) setChosen(null);
          }}
        />
      )}
    </div>
  );
}
