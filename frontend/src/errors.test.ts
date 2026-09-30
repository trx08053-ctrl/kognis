// Текст ошибки по коду сервера; неизвестный код — общий текст со статусом HTTP (kognis-b7x, AC2).
import { expect, test } from "vitest";
import { ApiError } from "./api";
import { describeError } from "./errors";
import { translate } from "./i18n";
import { ru } from "./i18n/ru";

const t = (key: Parameters<typeof translate>[2], params?: Record<string, string | number>) =>
  translate(ru, "ru", key, params);

test("известный код показывается текстом словаря с параметрами", () => {
  const error = new ApiError("user.password_short", 422, { min: 8 });
  expect(describeError(t, error)).toBe("Пароль должен быть не короче 8 символов");
});

test("неизвестный код — общий текст с HTTP-статусом", () => {
  expect(describeError(t, new ApiError("no.such_code", 418))).toBe("ошибка 418");
});

test("ответ без кода — общий текст с HTTP-статусом", () => {
  expect(describeError(t, new ApiError(null, 502))).toBe("ошибка 502");
});

test("ошибка клиента: ключ словаря переводится, прочий текст остаётся как есть", () => {
  expect(describeError(t, new Error("error.private.wrong_password"))).toContain("Неверный пароль");
  expect(describeError(t, new TypeError("Failed to fetch"))).toBe("Failed to fetch");
});
