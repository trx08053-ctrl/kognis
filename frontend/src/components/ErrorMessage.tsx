import { describeError } from "../errors";
import { useI18n } from "../i18n";

// текст — по коду ошибки сервера или ключу словаря (ошибки клиента, напр. privateCrypto)
export function ErrorMessage({ error }: { error: Error | null }) {
  const { t } = useI18n();
  if (!error) return null;
  return (
    <p className="mt-2 font-semibold text-[var(--danger-text)]" role="alert">
      {describeError(t, error)}
    </p>
  );
}
