# PROGRESS kognis-b7x

## Сделано
- Шаг 1 (коды ошибок): `kognis.errors` (`CodedError`, `CodedValueError`), все исключения для показа несут `code`/`params`,
  `web/_errors.py::http_error` → `{"detail": {"code","params"}}`; фронтенд: `errors.ts::describeError`, словарь `error.<код>`
  в `ru.ts`, `ApiError.code/params`. Тесты: `tests/web/test_error_codes.py` (AC1, AC2), старые тесты переведены на коды.
- Заметка: первая буква ошибок стала заглавной (текст из словаря, было: фраза сервера со строчной) — e2e-тесты обновлены.
- Доказательство: `just verify` OK · tree 8e221150a867.

## Следующий шаг
Шаг 2 (locale): миграция 0014 `users.locale` (nullable, default ru), `User.locale`, `validate_locale`/`pick_locale`
(Accept-Language) в `users`, `UserOut.locale`, `SettingsIn.locale` (422 `user.locale_unsupported`), `just api-types`,
фронтенд берёт язык из `/api/me`; тесты AC3 (`tests/users/test_locale.py`, миграция вверх/вниз), AC4
(`tests/security/test_locale_access.py`); затем reviewer → REVIEW.md → `python3 scripts/task.py done kognis-b7x`.
