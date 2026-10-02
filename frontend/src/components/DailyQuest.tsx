// Мотивация 2.0 (4/4): квест дня — выбор 1 из 3 лёгких, без штрафа за невыполнение;
// рядом — недельный квест от наставника. При кризисе на экране блока нет (ADR 0006).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptQuest,
  chooseDailyQuest,
  completeDailyQuest,
  type Daily,
  getDailyQuest,
  listQuestLibrary,
} from "../api";
import { isKey, type Key, useI18n } from "../i18n";
import { ErrorMessage } from "./ErrorMessage";

function useDailyText() {
  const { t } = useI18n();
  // коды заданий приходят с сервера: неизвестный код — пустая строка, не ошибка
  return (key: string) => (isKey(key) ? t(key as Key) : "");
}

function WeeklyHint({ weekly }: { weekly: string | null }) {
  const { t } = useI18n();
  const client = useQueryClient();
  const library = useQuery({
    queryKey: ["quest-library"],
    queryFn: listQuestLibrary,
    retry: false,
  });
  const take = useMutation({
    mutationFn: () => acceptQuest(weekly as string),
    onSuccess: () => client.invalidateQueries({ queryKey: ["quests"] }),
  });
  if (!weekly) return null;
  const template = library.data?.find((q) => q.code === weekly);
  return (
    <p className="text-sm muted" data-testid="daily-weekly">
      {t("daily.weekly")}: <span className="font-semibold">{template?.title ?? weekly}</span>{" "}
      <button
        type="button"
        className="link"
        disabled={take.isPending}
        onClick={() => take.mutate()}
      >
        {t("daily.weekly.take")}
      </button>
      <ErrorMessage error={take.error} />
    </p>
  );
}

export function DailyQuest({ crisis = false }: { crisis?: boolean }) {
  const { t } = useI18n();
  const text = useDailyText();
  const client = useQueryClient();
  const daily = useQuery({ queryKey: ["daily-quest"], queryFn: getDailyQuest, retry: false });
  const choose = useMutation({
    mutationFn: chooseDailyQuest,
    onSuccess: (state: Daily) => {
      client.setQueryData(["daily-quest"], state);
      client.invalidateQueries({ queryKey: ["progress"] });
    },
  });
  const done = useMutation({
    mutationFn: completeDailyQuest,
    onSuccess: (state: Daily) => {
      client.setQueryData(["daily-quest"], state);
      client.invalidateQueries({ queryKey: ["progress"] });
      client.invalidateQueries({ queryKey: ["sparks"] });
    },
  });
  if (crisis) return null;
  if (daily.error) return <ErrorMessage error={daily.error} />;
  if (!daily.data) return null;
  const data = daily.data;
  return (
    <section aria-labelledby="daily-title" className="card space-y-3" data-testid="daily-quest">
      <h2 id="daily-title" className="text-xl font-semibold">
        {t("daily.title")}
      </h2>
      {data.picked ? (
        <>
          <p data-testid="daily-picked">{text(`daily.option.${data.picked}`)}</p>
          {data.done ? (
            <p className="text-sm" data-testid="daily-done">
              {t("daily.done")}
            </p>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={done.isPending}
              onClick={() => done.mutate()}
            >
              {t("daily.mark")}
            </button>
          )}
        </>
      ) : (
        <>
          <p className="text-sm muted">{t("daily.choose")}</p>
          <ul className="grid gap-2 sm:grid-cols-3">
            {data.options.map((code) => (
              <li key={code} className="card-sm">
                <button
                  type="button"
                  className="link"
                  data-testid={`daily-option-${code}`}
                  disabled={choose.isPending}
                  onClick={() => choose.mutate(code)}
                >
                  {text(`daily.option.${code}`)}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <ErrorMessage error={choose.error} />
      <ErrorMessage error={done.error} />
      <WeeklyHint weekly={data.weekly} />
    </section>
  );
}
