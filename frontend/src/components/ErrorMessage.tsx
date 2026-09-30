import { isKey, useI18n } from "../i18n";

// сообщение — либо ключ словаря (ошибки клиента, напр. privateCrypto), либо готовый текст сервера
export function ErrorMessage({ error }: { error: Error | null }) {
  const { t } = useI18n();
  if (!error) return null;
  return (
    <p className="mt-2 font-semibold text-[var(--danger-text)]" role="alert">
      {isKey(error.message) ? t(error.message) : error.message}
    </p>
  );
}
