# REVIEW kognis-b7x

Раунд 1 (subagent reviewer): blocker — нет; VERDICT: changes.

Замечания и устранение:
- major: ошибки схемы pydantic отдавали список с английским `msg` и эхом `input` → добавлен обработчик
  `RequestValidationError` (`{"code": "request.validation"}`), случай в `CASES` (`POST /api/auth/register {}`).
- major: эффект языка профиля перебивал бы ручной выбор языка → применяется один раз на значение профиля (`useRef`).
- minor (принято, не правится): тест кодов по regex не видит f-string коды `diary.{what}_*` (они перечислены в словаре
  вручную); русский блок помощи/названия направлений — не исключения, следующие задачи серии; `host` в
  `ai.network_*` берётся из конфигурации провайдера.

Не проверено ревьюером: фактический diff, `just verify`, e2e, PostgreSQL-миграция.

Раунд 2 (subagent reviewer, повторный запуск): blocker/major — нет; VERDICT: approve.
- minor (устранено): добавлен тест «ручной выбор языка после применения профиля не перебивается»
  (`frontend/src/profileLocale.test.tsx`).
Не проверено ревьюером: свежесть `just verify`, e2e, миграция на PostgreSQL, мутационное тестирование.

VERDICT: approve
