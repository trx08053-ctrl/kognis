import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { type DayReview, listDayReviews, saveDayReview } from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { HelpPanel } from "../components/HelpPanel";
import { type Mark, MarksField } from "../components/MarksField";
import { ScaleField } from "../components/ScaleField";
import { useToday } from "../dates";

const inputClass = "input";
const buttonClass = "btn";

function DayReviewForm() {
  const client = useQueryClient();
  const today = useToday();
  const [date, setDate] = useState(today);
  const [wellbeing, setWellbeing] = useState("5");
  const [mood, setMood] = useState("5");
  const [reflection, setReflection] = useState("");
  const [marks, setMarks] = useState<Mark[]>([]);
  const save = useMutation({
    mutationFn: () =>
      saveDayReview(date, { wellbeing: Number(wellbeing), mood: Number(mood), reflection, marks }),
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
      <MarksField value={marks} onChange={setMarks} />
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
  const reviews = useInfiniteQuery({
    queryKey: ["day-reviews", "history"],
    queryFn: ({ pageParam }) => listDayReviews({ cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next,
  });
  if (reviews.isError) return <ErrorMessage error={reviews.error} />;
  const items: DayReview[] = reviews.data?.pages.flatMap((page) => page.items) ?? [];
  if (items.length === 0) return <p className="muted">Пока нет итогов дня.</p>;
  return (
    <>
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
      {reviews.hasNextPage && (
        <button
          type="button"
          className={buttonClass}
          data-testid="more-reviews"
          disabled={reviews.isFetchingNextPage}
          onClick={() => void reviews.fetchNextPage()}
        >
          Показать ещё
        </button>
      )}
    </>
  );
}

export function DayReviewPage() {
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
