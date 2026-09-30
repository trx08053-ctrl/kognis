import { useQuery } from "@tanstack/react-query";
import { getProgress } from "../api";
import { TrophyIcon } from "../Icons";
import { useI18n } from "../i18n";
import { ErrorMessage } from "./ErrorMessage";

export function useProgress() {
  return useQuery({ queryKey: ["progress"], queryFn: getProgress });
}

export function ProgressWidget() {
  const { t } = useI18n();
  const progress = useProgress();
  if (progress.isError) return <ErrorMessage error={progress.error} />;
  const data = progress.data;
  if (!data) return null;
  const span = data.next_level_xp - data.level_start_xp;
  const done = Math.min(span, data.xp - data.level_start_xp);
  return (
    <section aria-label={t("progress.title")} data-testid="progress" className="space-y-2 card">
      <div
        className="meter"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={span}
        aria-valuenow={done}
        aria-label={t("progress.level_aria", { done, span })}
      >
        <div style={{ width: `${span > 0 ? (done / span) * 100 : 0}%` }} />
      </div>
      <p className="text-sm muted" data-testid="xp">
        {t("progress.xp", { xp: data.xp, next: data.next_level_xp })}
      </p>
    </section>
  );
}

export function Achievements() {
  const { t, formatDate } = useI18n();
  const progress = useProgress();
  const earned = progress.data?.achievements ?? [];
  return (
    <section aria-labelledby="achievements-title" className="space-y-3">
      <h3 id="achievements-title" className="text-lg font-semibold">
        {t("achievements.title")}
      </h3>
      <ErrorMessage error={progress.error} />
      {progress.data && earned.length === 0 && <p>{t("achievements.empty")}</p>}
      <ul className="space-y-2" data-testid="achievements">
        {earned.map((a) => (
          <li key={a.code} className="card-sm flex items-start gap-3">
            <span className="badge !p-2" aria-hidden="true">
              <TrophyIcon />
            </span>
            <div>
              <p className="font-semibold">{a.title}</p>
              <p className="text-sm muted">{a.description}</p>
              <p className="text-sm muted">
                {t("achievements.earned")}{" "}
                <time dateTime={a.earned_on}>{formatDate(a.earned_on)}</time>
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
