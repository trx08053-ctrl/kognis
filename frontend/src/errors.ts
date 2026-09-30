// Текст ошибки для человека: по коду сервера (`error.<код>`), иначе общий текст со статусом HTTP.
import { ApiError } from "./api";
import { type I18n, isKey } from "./i18n";

export function describeError(t: I18n["t"], error: Error): string {
  if (error instanceof ApiError) {
    const key = `error.${error.code}`;
    if (error.code !== null && isKey(key)) return t(key, error.params);
    return t("error.unknown", { status: error.status });
  }
  // ошибки клиента: ключ словаря (privateCrypto) или готовый текст страницы (вынос — задачи серии i18n)
  return isKey(error.message) ? t(error.message) : error.message;
}
