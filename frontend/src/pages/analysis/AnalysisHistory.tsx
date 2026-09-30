import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { type Analysis, type Direction, deleteAnalysis } from "../../api";
import { ErrorMessage } from "../../components/ErrorMessage";
import { useI18n } from "../../i18n";

const buttonClass = "btn";

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

export function AnalysisHistory({
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
