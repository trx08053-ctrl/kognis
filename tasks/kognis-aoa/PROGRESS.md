# PROGRESS kognis-aoa

## Сделано
- Логотип в шапке `Shell` — ссылка на `/welcome` (aria-label из словаря, видимый фокус).
- `/welcome` для вошедшего: `LandingPage signedIn` — вместо форм и кнопок входа «Открыть дневник»; гость на `/` без изменений.
- Тесты: `tests/e2e/test_logo_nav.py` (AC1, AC2), vitest `pages.test.tsx` через `tests/web/test_i18n_frontend.py` (AC3).
- Доказательство: `just verify` OK, tree 003033ae1c02.

## Следующий шаг
Ревью (subagent `reviewer`) → `tasks/kognis-aoa/REVIEW.md`, затем `python3 scripts/task.py done kognis-aoa`.
