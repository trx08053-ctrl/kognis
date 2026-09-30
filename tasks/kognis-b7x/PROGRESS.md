# PROGRESS kognis-b7x

## Сделано
- Шаг 1 (коды ошибок): `kognis.errors` (`CodedError`, `CodedValueError`), все исключения для показа несут `code`/`params`,
  `web/_errors.py::http_error` → `{"detail": {"code","params"}}`; фронтенд: `errors.ts::describeError`, словарь `error.<код>`
  в `ru.ts`, `ApiError.code/params`. Тесты: `tests/web/test_error_codes.py` (AC1, AC2), старые тесты переведены на коды.
  Первая буква ошибок стала заглавной (текст из словаря; раньше — фраза сервера со строчной), e2e-тесты обновлены.
- Шаг 2 (locale): миграция 0014 `users.locale` (nullable, default ru), `User.locale`, `validate_locale`/`pick_locale`
  (Accept-Language), `UserOut.locale`, `PUT /api/me/settings` принимает `locale` (422 `user.locale_unsupported`),
  `api.gen.ts`, фронтенд берёт язык из `/api/me` (`App.tsx`). Тесты: `tests/users/test_locale.py` (AC3),
  `tests/security/test_locale_access.py` (AC4), `frontend/src/profileLocale.test.tsx`.
- Доказательство: `just verify` OK · tree 4dda371bd5b2.

## Следующий шаг
Ревью: subagent `reviewer` → `tasks/kognis-b7x/REVIEW.md`, устранить blocker/major, затем
`python3 scripts/task.py done kognis-b7x`.
