import { useQuery } from "@tanstack/react-query";
import { getProgress, type Progress } from "../api";
import { TrophyIcon } from "../Icons";
import { isKey, type Key, useI18n } from "../i18n";
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

// ключ словаря из кода с сервера; неизвестный код не ломает экран
function dictKey(value: string): Key {
  return isKey(value) ? value : "achievements.locked";
}

function CategoryGrid({ category }: { category: Progress["categories"][number] }) {
  const { t, formatDate } = useI18n();
  const name = t(dictKey(`achievements.category.${category.category}`));
  return (
    <section
      aria-label={name}
      data-testid={`category-${category.category}`}
      className="card-sm space-y-2"
    >
      <h4 className="font-semibold">{name}</h4>
      <p className="text-sm muted">
        {t(dictKey(`achievements.category.${category.category}_hint`))}
      </p>
      <p className="text-sm" data-testid={`category-${category.category}-progress`}>
        {category.next_target === null
          ? t("achievements.complete")
          : t("achievements.progress", { value: category.value, target: category.next_target })}
      </p>
      <ul className="grid grid-cols-3 gap-2">
        {category.levels.map((level) => (
          <li
            key={level.code}
            data-testid={level.code}
            data-earned={level.earned_on ? "yes" : "no"}
            className={level.earned_on ? "badge" : "muted"}
          >
            <span className="font-semibold">{t(dictKey(`achievements.level.${level.level}`))}</span>{" "}
            {level.earned_on ? (
              <time dateTime={level.earned_on}>{formatDate(level.earned_on)}</time>
            ) : (
              <span className="text-sm">{t("achievements.locked")}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function HiddenGrid({ hidden }: { hidden: Progress["hidden"] }) {
  const { t, formatDate } = useI18n();
  return (
    <ul className="grid grid-cols-3 gap-2" data-testid="hidden-achievements">
      {hidden.map((h) => (
        <li
          key={h.code}
          data-testid={`hidden-${h.code}`}
          className="card-sm"
          title={h.earned_on ? undefined : t("achievements.hidden_hint")}
        >
          {h.earned_on ? (
            <>
              <span className="font-semibold">{t(dictKey(`achievements.hidden.${h.code}`))}</span>{" "}
              <time dateTime={h.earned_on}>{formatDate(h.earned_on)}</time>
            </>
          ) : (
            t("achievements.hidden_title")
          )}
        </li>
      ))}
    </ul>
  );
}

export function Achievements() {
  const { t, formatDate } = useI18n();
  const progress = useProgress();
  // в сетку и скрытые входят новые достижения; остальные — прежней версии, их показываем списком
  const shown = new Set([
    ...(progress.data?.categories ?? []).flatMap((c) => c.levels.map((l) => l.code)),
    ...(progress.data?.hidden ?? []).map((h) => h.code),
  ]);
  const earned = (progress.data?.achievements ?? []).filter((a) => !shown.has(a.code));
  return (
    <section aria-labelledby="achievements-title" className="space-y-3">
      <h3 id="achievements-title" className="text-lg font-semibold">
        {t("achievements.title")}
      </h3>
      <ErrorMessage error={progress.error} />
      {progress.data && (
        <div className="grid gap-3 sm:grid-cols-2" data-testid="achievement-grid">
          {progress.data.categories.map((c) => (
            <CategoryGrid key={c.category} category={c} />
          ))}
        </div>
      )}
      {progress.data && <HiddenGrid hidden={progress.data.hidden} />}
      {earned.length > 0 && <h4 className="font-semibold">{t("achievements.legacy")}</h4>}
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
