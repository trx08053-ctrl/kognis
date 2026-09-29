# PROGRESS kognis-e7s

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Дождаться повторного ревью (subagent `reviewer`, diff 9518f24..HEAD); дописать его ответ как «Ревью 2» в `tasks/kognis-e7s/REVIEW.md`, устранить blocker/major; при `VERDICT: approve` выполнить `python3 scripts/task.py done kognis-e7s`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | /health с SELECT 1 (503 без деталей), docs/redoc/openapi только при KOGNIS_ENV=dev, RUNBOOK без ручного pg_dump, тесты AC1–AC3 (tests/web/test_operations.py) | 9518f24 | just verify OK, tree e667deb3ba65, evidence .evidence/e667deb3ba65432f1926f095862a21baa8277f87.json |
| 2026-09-29 | Ревью 1 (MAJOR: карточка web) устранено: docs/modules/web.md, лог класса ошибки в /health, строже тест AC3; REVIEW.md | 9c117ab | just verify OK, tree 6eb1878fdebf, evidence .evidence/6eb1878fdebf639ceeee8ef364055df23cd8e4d6.json |

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- Первый вариант `FastAPI(**docs)` не прошёл `types` (pyright) — заменён явными параметрами `docs_url`/`redoc_url`/`openapi_url`.
- Catch-all маршрут SPA отдавал бы страницу на /docs вне dev — добавлен 404 для DOC_PATHS.

## Затраты
Сессии: 1 · $~0.4 · время __
