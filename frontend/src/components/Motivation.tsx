import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { type Progress, recoverStreak, saveProgressSettings } from "../api";
import { useI18n } from "../i18n";
import { ErrorMessage } from "./ErrorMessage";
import { useProgress } from "./Progress";

const GOALS = [3, 5, 7];
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const;
const MAX_WEEKEND_DAYS = 2;

function useProgressMutation<V>(fn: (value: V) => Promise<Progress>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (saved) => client.setQueryData(["progress"], saved),
  });
}

// обрыв серии — не «0», а предложение вернуть её короткой заметкой (окно 72 часа)
function RecoveryOffer({ offer }: { offer: NonNullable<Progress["recovery"]> }) {
  const { t, formatDate } = useI18n();
  const [note, setNote] = useState("");
  const recover = useProgressMutation(recoverStreak);
  return (
    <form
      className="card-sm space-y-2"
      data-testid="recovery"
      onSubmit={(event) => {
        event.preventDefault();
        recover.mutate(note);
      }}
    >
      <p className="font-semibold">
        {t("motivation.recovery_title", { days: offer.streak_before })}
      </p>
      <p className="text-sm muted">
        {t("motivation.recovery_until", { date: formatDate(offer.expires_on) })}
      </p>
      <label htmlFor="recovery-note" className="font-semibold">
        {t("motivation.recovery_label")}
      </label>
      <input
        id="recovery-note"
        className="input"
        maxLength={500}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <button type="submit" className="btn" disabled={note.trim() === "" || recover.isPending}>
        {t("motivation.recovery_button")}
      </button>
      <ErrorMessage error={recover.error} />
    </form>
  );
}

function GoalAndWeekend({ data }: { data: Progress }) {
  const { t } = useI18n();
  const save = useProgressMutation(saveProgressSettings);
  const toggleDay = (day: number) => {
    const chosen = data.weekend_days.includes(day)
      ? data.weekend_days.filter((d) => d !== day)
      : [...data.weekend_days, day];
    save.mutate({ weekend_days: chosen, weekly_goal: data.weekly_goal });
  };
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <label htmlFor="weekly-goal" className="font-semibold">
          {t("motivation.goal_choice")}
        </label>
        <select
          id="weekly-goal"
          data-testid="weekly-goal"
          className="input !w-auto"
          value={data.weekly_goal}
          onChange={(event) =>
            save.mutate({
              weekend_days: data.weekend_days,
              weekly_goal: Number(event.target.value),
            })
          }
        >
          {GOALS.map((goal) => (
            <option key={goal} value={goal}>
              {t("motivation.goal_option", { count: goal })}
            </option>
          ))}
        </select>
        <p className="text-sm muted">{t("motivation.goal_hint")}</p>
      </div>
      <fieldset className="space-y-1">
        <legend className="font-semibold">{t("motivation.weekend_title")}</legend>
        <div className="flex flex-wrap gap-3">
          {WEEKDAYS.map((day) => {
            const checked = data.weekend_days.includes(day);
            return (
              <label key={day} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-[var(--accent)]"
                  data-testid={`weekend-${day}`}
                  checked={checked}
                  disabled={!checked && data.weekend_days.length >= MAX_WEEKEND_DAYS}
                  onChange={() => toggleDay(day)}
                />
                {t(`weekday.${day}`)}
              </label>
            );
          })}
        </div>
        <p className="text-sm muted">{t("motivation.weekend_hint")}</p>
      </fieldset>
      <ErrorMessage error={save.error} />
    </div>
  );
}

// экран прогресса: главное — дни с дневником, а не серия; серия вторична и никогда не «0»
export function MotivationPanel() {
  const { t } = useI18n();
  const progress = useProgress();
  const data = progress.data;
  if (!data) return null;
  return (
    <section aria-labelledby="motivation-title" className="card space-y-3" data-testid="motivation">
      <h3 id="motivation-title" className="text-lg font-semibold">
        {t("motivation.title")}
      </h3>
      <p className="text-xl font-bold" data-testid="days-30">
        {t("motivation.days_30", { count: data.days_30 })}
      </p>
      <p data-testid="days-total">{t("motivation.days_total", { count: data.days_total })}</p>
      {data.streak > 0 ? (
        <p data-testid="streak-line">{t("motivation.streak", { days: data.streak })}</p>
      ) : (
        <p className="muted">{t("motivation.no_streak")}</p>
      )}
      {data.best_streak > 0 && (
        <p className="muted">{t("motivation.best", { days: data.best_streak })}</p>
      )}
      <p data-testid="freezes">{t("motivation.freezes", { count: data.freezes })}</p>
      <p className="text-sm muted">{t("motivation.freezes_hint")}</p>
      {data.recovery && <RecoveryOffer offer={data.recovery} />}
      <div data-testid="weekly">
        <p className="font-semibold">{t("motivation.goal_title")}</p>
        <p>{t("motivation.goal_progress", { done: data.week_days, goal: data.weekly_goal })}</p>
        {data.week_days >= data.weekly_goal && (
          <p className="font-semibold" data-testid="goal-done">
            {t("motivation.goal_done")}
          </p>
        )}
      </div>
      <GoalAndWeekend data={data} />
    </section>
  );
}
