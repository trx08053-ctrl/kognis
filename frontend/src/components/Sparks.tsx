// Мотивация 2.0 (4/4): искры — баланс, витрина косметики и заморозки. Прогресс, разборы
// и аналитика за искры не продаются (ADR 0006); при кризисе на экране блока искр нет.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSparks, purchaseItem, type Sparks } from "../api";
import { isKey, type Key, useI18n } from "../i18n";
import { ErrorMessage } from "./ErrorMessage";

function useText() {
  const { t } = useI18n();
  // коды товаров приходят с сервера: неизвестный код — пустая строка, не ошибка
  return (key: string) => (isKey(key) ? t(key as Key) : "");
}

export function useSparks() {
  return useQuery({ queryKey: ["sparks"], queryFn: getSparks, retry: false });
}

// купленный аксессуар меняет облик спутника; из нескольких — первый по каталогу
export function useOwnedAccessory(): string | null {
  const sparks = useSparks();
  const owned = sparks.data?.catalog.find((i) => i.kind === "accessory" && i.owned);
  return owned?.code ?? null;
}

function Position({
  item,
  onBuy,
  pending,
}: {
  item: Sparks["catalog"][number];
  onBuy: (code: string) => void;
  pending: boolean;
}) {
  const { t } = useI18n();
  const text = useText();
  return (
    <li className="card-sm space-y-1" data-testid={`shop-${item.code}`}>
      <p className="font-semibold">{text(`spark.item.${item.code}`)}</p>
      <p className="text-sm muted">{text(`spark.item.${item.code}.hint`)}</p>
      <p className="text-sm">
        {t("spark.price", { count: item.price })}
        {item.kind === "freeze" && (
          <span className="muted"> · {t("spark.item.freeze.note", { max: 2 })}</span>
        )}
      </p>
      {item.owned ? (
        <p className="text-sm" data-testid={`shop-${item.code}-owned`}>
          {t("spark.owned")}
        </p>
      ) : (
        <button type="button" className="btn" disabled={pending} onClick={() => onBuy(item.code)}>
          {t("spark.buy")}
        </button>
      )}
    </li>
  );
}

export function SparksPanel({ crisis = false }: { crisis?: boolean }) {
  const { t } = useI18n();
  const client = useQueryClient();
  const sparks = useSparks();
  const buy = useMutation({
    mutationFn: purchaseItem,
    onSuccess: (state) => {
      client.setQueryData(["sparks"], state);
      client.invalidateQueries({ queryKey: ["progress"] });
    },
  });
  if (crisis) return null; // игровая механика рядом с кризисным контентом не показывается
  if (sparks.error) return <ErrorMessage error={sparks.error} />;
  if (!sparks.data) return null;
  const data = sparks.data;
  return (
    <section aria-labelledby="sparks-title" className="card space-y-3" data-testid="sparks">
      <h2 id="sparks-title" className="text-xl font-semibold">
        {t("spark.title")}
      </h2>
      <p className="text-sm" data-testid="sparks-balance">
        {t("spark.balance", { count: data.balance })}
      </p>
      <p className="text-sm muted">{t("spark.earn")}</p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {data.catalog.map((item) => (
          <Position key={item.code} item={item} onBuy={buy.mutate} pending={buy.isPending} />
        ))}
      </ul>
      <ErrorMessage error={buy.error} />
    </section>
  );
}
