# PROGRESS kognis-3mh

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Ревью (subagent `reviewer`) → записать ответ в `tasks/kognis-3mh/REVIEW.md`, устранить blocker/major, затем
`python3 scripts/task.py done kognis-3mh`. AC4 (замер на staging по RUNBOOK «Производительность») — за техответственным:
занести p95 в таблицу RUNBOOK и сюда.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | Курсорная пагинация `GET /api/entries`, `/api/day-reviews` (30/100, `X-Next-Cursor`), фильтры tag/emotion/from/to в SQL, `/api/entries/labels`, индекс `ix_entries_owner_date_id` (миграция 0013), «Показать ещё» во фронтенде, `scripts/seed_perf.py`, НФТ в ARCHITECTURE §6, замеры в RUNBOOK | af91ff7 | `just verify` OK · tree e65ebfbc6518; AC1/AC2 — `tests/web/test_pagination.py`, AC3 — `tests/e2e/test_paging.py` |

## Решения
- Тело ответа списков осталось массивом, курсор — в заголовке `X-Next-Cursor`: контракт для клиентов не ломается (конверт `{items, next}` был бы ломающим изменением — решение человека).
- Курсор «дата.id» (записи) / «дата» (итоги), не смещение: новые записи между запросами не сдвигают страницу.
- RTO ≤ 1 ч в таблице НФТ — предложенная цель (в проекте не была зафиксирована); техответственный подтверждает или правит.

## Блокеры и вопросы человеку
- AC4: замер на staging (в песочнице агента нет Docker). Команды — RUNBOOK, раздел «Производительность: замер бюджетов».
- Интеграционный тест на Postgres (`test_paging_and_label_filters_on_postgres`) в песочнице не запускался (нет Docker) — пройдёт в CI.

## Попытки и гипотезы (что пробовали и почему не сработало)
- `include_router` с пустым путём при пустом prefix запрещён FastAPI → страницы регистрируются на общем роутере (`add_entry_pages`).
- Ограничение `test_api_types_come_from_generated_schema` запрещает `interface` в `api.ts` → клиентские типы страниц вынесены в `frontend/src/pagination.ts`.

## Затраты
Сессии: 1 · $≈3.8 · время ≈ 1 ч
