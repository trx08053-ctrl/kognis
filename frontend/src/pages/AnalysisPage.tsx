import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import {
  type Analysis,
  ApiError,
  acceptQuestFromAnalysis,
  answerAnalysis,
  clearMemory,
  type Direction,
  getAnalysis,
  getDefaultPeriod,
  getMemory,
  getMood,
  listAnalyses,
  listDirections,
  runAnalysis,
} from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { HelpPanel } from "../components/HelpPanel";
import { MentorLine } from "../components/Heroes";
import { shiftDay, useToday } from "../dates";
import { useI18n } from "../i18n";
import { AnalysisHistory } from "./analysis/AnalysisHistory";

const MAX_PERIOD_DAYS = 31; // совпадает с лимитом сервера (analysis.period_long)
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
      <MentorLine direction={analysis.direction} />
      <p>{analysis.summary}</p>
      {analysis.changes.length > 0 && (
        <section aria-labelledby={`changes-${analysis.id}`} data-testid="analysis-changes">
          <h4 id={`changes-${analysis.id}`} className="font-semibold">
            {t("analysis.changes.title")}
          </h4>
          <ul className="list-disc ps-5">
            {analysis.changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </section>
      )}
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

// «Что ИИ помнит обо мне»: дайджест виден человеку и очищается кнопкой (152-ФЗ)
function MemoryPanel() {
  const { t } = useI18n();
  const client = useQueryClient();
  const memory = useQuery({ queryKey: ["analysis-memory"], queryFn: getMemory });
  const clear = useMutation({
    mutationFn: clearMemory,
    onSuccess: () => client.invalidateQueries({ queryKey: ["analysis-memory"] }),
  });
  const digest = memory.data?.digest ?? "";
  return (
    <section aria-labelledby="memory-title" className="space-y-2" data-testid="ai-memory">
      <h3 id="memory-title" className="text-lg font-semibold">
        {t("analysis.memory.title")}
      </h3>
      <p className="text-sm muted">{t("analysis.memory.hint")}</p>
      {digest ? (
        <>
          <p className="whitespace-pre-wrap" data-testid="ai-memory-digest">
            {digest}
          </p>
          <button
            type="button"
            className="link"
            disabled={clear.isPending}
            onClick={() => clear.mutate()}
          >
            {t("analysis.memory.clear")}
          </button>
        </>
      ) : (
        <p className="muted">
          {clear.isSuccess ? t("analysis.memory.cleared") : t("analysis.memory.empty")}
        </p>
      )}
      <ErrorMessage error={memory.error ?? clear.error} />
    </section>
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

export function AnalysisPage() {
  const { t } = useI18n();
  const today = useToday();
  const client = useQueryClient();
  // период по умолчанию — от конца прошлого разбора; ручной выбор его перекрывает
  const period = useQuery({ queryKey: ["analysis-period"], queryFn: getDefaultPeriod });
  const suggested = period.data ?? null;
  const [manual, setManual] = useState<{ start: string; end: string } | null>(null);
  const start = manual?.start ?? suggested?.start ?? shiftDay(today, -6);
  const end = manual?.end ?? suggested?.end ?? today;
  const idle = manual === null && suggested !== null && !suggested.active;
  const [direction, setDirection] = useState("cbt");
  const [consent, setConsent] = useState(false);
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
    void client.invalidateQueries({ queryKey: ["analysis-period"] });
    void client.invalidateQueries({ queryKey: ["analysis-memory"] });
  };
  const run = useMutation({
    mutationFn: () => runAnalysis({ direction, start, end, consent }),
    onSuccess: (analysis) => {
      setManual(null);
      show(analysis);
    },
  });
  const openById = useMutation({ mutationFn: getAnalysis, onSuccess: setChosen });
  const duplicateId =
    run.error instanceof ApiError && run.error.code === "analysis.duplicate"
      ? Number(run.error.params.existing_id)
      : null;
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
              onChange={(event) => setManual({ start: event.target.value, end })}
            />
          </div>
          <div>
            <label htmlFor="analysis-end">По дату</label>
            <input
              id="analysis-end"
              type="date"
              className={inputClass}
              value={end}
              onChange={(event) => setManual({ start, end: event.target.value })}
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
        {manual && (
          <button type="button" className="link mt-2" onClick={() => setManual(null)}>
            {t("analysis.period.reset")}
          </button>
        )}
      </details>
      {idle && (
        <p data-testid="analysis-no-new">
          {t("analysis.period.no_new")}{" "}
          {suggested?.last_analysis_id != null && (
            <button
              type="button"
              className="link"
              onClick={() => openById.mutate(suggested.last_analysis_id as number)}
            >
              {t("analysis.period.open_last")}
            </button>
          )}
        </p>
      )}
      {!manual && suggested?.truncated && (
        <p className="text-sm">{t("analysis.period.truncated", { max: MAX_PERIOD_DAYS })}</p>
      )}
      <button
        type="button"
        className={buttonClass}
        data-testid="run-analysis"
        disabled={run.isPending || !consent || idle}
        onClick={() => run.mutate()}
      >
        {run.isPending ? "Разбираю…" : "Разобрать неделю"}
      </button>
      {!consent && <p className="text-sm">Отметьте согласие, чтобы запустить разбор.</p>}
      <ErrorMessage error={run.error} />
      {duplicateId !== null && (
        <button type="button" className="link" onClick={() => openById.mutate(duplicateId)}>
          {t("analysis.duplicate.open")}
        </button>
      )}
      <ErrorMessage error={openById.error} />
      <MoodSummary start={start} end={end} />
      {result && (
        <>
          <AnalysisView analysis={result} directions={list} />
          <FollowUp key={result.id} analysis={result} consent={consent} onDone={show} />
        </>
      )}
      <MemoryPanel />
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
