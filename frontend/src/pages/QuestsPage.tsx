import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import {
  acceptQuest,
  completeQuestStep,
  listQuestLibrary,
  listQuests,
  listQuizzes,
  type Quest,
  type QuestTemplate,
  type Quiz,
  type QuizResult,
  submitQuiz,
} from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { MentorLine } from "../components/Heroes";

const inputClass = "input";
const buttonClass = "btn";

const KIND_TEXT = { quest: "Квест", challenge: "Челлендж" } as const;

const Problem = ErrorMessage;

function ActiveQuest({ quest }: { quest: Quest }) {
  const client = useQueryClient();
  const done = quest.steps.filter((s) => s.done_on !== null).length;
  const mark = useMutation({
    mutationFn: (idx: number) => completeQuestStep(quest.id, idx),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["quests"] }),
        client.invalidateQueries({ queryKey: ["progress"] }),
      ]),
  });
  return (
    <li className="card-sm" data-testid="quest">
      <p className="font-semibold">
        {quest.title} <span className="text-sm font-normal muted">({KIND_TEXT[quest.kind]})</span>
      </p>
      <p className="text-sm muted" data-testid="quest-progress">
        {quest.completed_on
          ? `Завершён ${quest.completed_on}`
          : `Выполнено шагов: ${done} из ${quest.steps.length}`}
      </p>
      <div
        className="meter mt-2"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={quest.steps.length}
        aria-valuenow={done}
        aria-label={`Шагов выполнено: ${done} из ${quest.steps.length}`}
      >
        <div
          style={{ width: `${quest.steps.length > 0 ? (done / quest.steps.length) * 100 : 0}%` }}
        />
      </div>
      <ol className="mt-2 space-y-1">
        {quest.steps.map((step) => (
          <li key={step.idx} className="flex items-center justify-between gap-3">
            <span className={step.done_on ? "muted line-through" : ""}>{step.title}</span>
            {step.done_on ? (
              <span className="text-sm muted">выполнено</span>
            ) : (
              <button
                type="button"
                className="link"
                aria-label={`Отметить шаг: ${step.title}`}
                disabled={mark.isPending}
                onClick={() => mark.mutate(step.idx)}
              >
                Отметить
              </button>
            )}
          </li>
        ))}
      </ol>
      <Problem error={mark.error} />
    </li>
  );
}

function Library({ active }: { active: Quest[] }) {
  const client = useQueryClient();
  const library = useQuery({ queryKey: ["quest-library"], queryFn: listQuestLibrary });
  const take = useMutation({
    mutationFn: (code: string) => acceptQuest(code),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["quests"] }),
        client.invalidateQueries({ queryKey: ["companion"] }),
      ]),
  });
  const open = new Set(active.filter((q) => !q.completed_on).map((q) => q.template_code));
  const items: QuestTemplate[] = library.data ?? [];
  // одна реплика наставника на экран: по направлению самого свежего принятого квеста из библиотеки
  const current = active.find((q) => q.template_code && !q.completed_on);
  const direction = items.find((t) => t.code === current?.template_code)?.direction;
  return (
    <section aria-labelledby="library-title" className="space-y-3">
      <h3 id="library-title" className="text-lg font-semibold">
        Библиотека квестов
      </h3>
      {direction && <MentorLine direction={direction} />}
      <Problem error={library.error} />
      <ul className="space-y-2" data-testid="library">
        {items.map((t) => (
          <li key={t.code} className="card-sm">
            <p className="font-semibold">
              {t.title}{" "}
              <span className="text-sm font-normal muted">
                ({KIND_TEXT[t.kind]}, шагов: {t.steps.length})
              </span>
            </p>
            <p className="text-sm muted">{t.description}</p>
            <button
              type="button"
              className={`${buttonClass} mt-2`}
              aria-label={`Принять: ${t.title}`}
              disabled={open.has(t.code) || take.isPending}
              onClick={() => take.mutate(t.code)}
            >
              {open.has(t.code) ? "Уже принят" : "Принять"}
            </button>
          </li>
        ))}
      </ul>
      <Problem error={take.error} />
    </section>
  );
}

function QuizCard({ quiz }: { quiz: Quiz }) {
  const client = useQueryClient();
  const [answers, setAnswers] = useState<string[]>(quiz.questions.map(() => ""));
  const [result, setResult] = useState<QuizResult | null>(null);
  const send = useMutation({
    mutationFn: () => submitQuiz(quiz.code, answers),
    onSuccess: (data) => {
      setResult(data);
      return Promise.all([
        client.invalidateQueries({ queryKey: ["quizzes"] }),
        client.invalidateQueries({ queryKey: ["progress"] }),
      ]);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    send.mutate();
  }

  const finished = quiz.done_today || result !== null;
  return (
    <li className="card-sm" data-testid="quiz">
      <p className="font-semibold">{quiz.title}</p>
      {finished ? (
        <div>
          <p className="text-sm muted" data-testid="quiz-done">
            {result ? `Ответы сохранены. Опыт: +${result.xp}.` : "Сегодня уже пройден."}
          </p>
          {result?.help && (
            <p role="note" className="mt-1">
              {result.help.message}{" "}
              {result.help.contacts.map((c) => (
                <a key={c.phone} href={`tel:${c.phone}`} className="link">
                  {c.phone}
                </a>
              ))}
            </p>
          )}
        </div>
      ) : (
        <form onSubmit={submit} className="mt-2 space-y-2">
          {quiz.questions.map((question, i) => (
            <div key={question}>
              <label htmlFor={`${quiz.code}-${i}`} className="block">
                {question}
              </label>
              <textarea
                id={`${quiz.code}-${i}`}
                className={inputClass}
                rows={2}
                value={answers[i]}
                onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))}
              />
            </div>
          ))}
          <button
            type="submit"
            className={buttonClass}
            disabled={send.isPending || answers.some((a) => a.trim() === "")}
          >
            Сохранить ответы
          </button>
          <Problem error={send.error} />
        </form>
      )}
    </li>
  );
}

export function QuestsPage() {
  const quests = useQuery({ queryKey: ["quests"], queryFn: listQuests });
  const quizzes = useQuery({ queryKey: ["quizzes"], queryFn: listQuizzes });
  const mine = quests.data ?? [];
  return (
    <section aria-labelledby="quests-title" className="space-y-6">
      <h2 id="quests-title" className="text-xl font-semibold">
        Квесты
      </h2>
      <section aria-labelledby="my-quests-title" className="space-y-3">
        <h3 id="my-quests-title" className="text-lg font-semibold">
          Мои квесты
        </h3>
        <Problem error={quests.error} />
        {quests.data && mine.length === 0 && <p>Пока нет квестов — выберите в библиотеке.</p>}
        <ul className="space-y-2" data-testid="my-quests">
          {mine.map((quest) => (
            <ActiveQuest key={quest.id} quest={quest} />
          ))}
        </ul>
      </section>
      <Library active={mine} />
      <section aria-labelledby="quizzes-title" className="space-y-3">
        <h3 id="quizzes-title" className="text-lg font-semibold">
          Квизы-рефлексии
        </h3>
        <Problem error={quizzes.error} />
        <ul className="space-y-2" data-testid="quizzes">
          {(quizzes.data ?? []).map((quiz) => (
            <QuizCard key={quiz.code} quiz={quiz} />
          ))}
        </ul>
      </section>
    </section>
  );
}
