# PROGRESS kognis-e7s

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Дождаться ответа subagent `reviewer` по коммиту 9518f24; записать его ответ в `tasks/kognis-e7s/REVIEW.md` (шаблон docs/templates/REVIEW.md), устранить blocker/major, повторить ревью до `VERDICT: approve`, затем `python3 scripts/task.py done kognis-e7s`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | /health с SELECT 1 (503 без деталей), docs/redoc/openapi только при KOGNIS_ENV=dev, RUNBOOK без ручного pg_dump, тесты AC1–AC3 (tests/web/test_operations.py) | 9518f24 | just verify OK, tree e667deb3ba65, evidence .evidence/e667deb3ba65432f1926f095862a21baa8277f87.json |

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- Первый вариант `FastAPI(**docs)` не прошёл `types` (pyright) — заменён явными параметрами `docs_url`/`redoc_url`/`openapi_url`.
- Catch-all маршрут SPA отдавал бы страницу на /docs вне dev — добавлен 404 для DOC_PATHS.

## Затраты
Сессии: 1 · $~0.4 · время __
