# PROGRESS kognis-zjg

## Следующий шаг
Ревью `reviewer` → `tasks/kognis-zjg/REVIEW.md`; blocker/major устранить, затем `just task-done kognis-zjg`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-10-01 | Домен героев, таблицы `companions`/`companion_postcards` (миграция 0018), сервис, API `/api/companion*` | `47847f8` | `tests/gameplay/test_heroes.py`, `tests/web/test_companion.py` (AC1–AC3) |
| 2026-10-01 | Интерфейс: SVG-герои, словарь `hero.*`, страницы Home/Analysis/Quests, витест-тесты (AC3, AC4) | (ветка task/kognis-zjg) | `src/heroes.test.tsx` 8 тестов |
| 2026-10-01 | e2e AC5: скриншоты светлая/тёмная тема + axe без serious/critical | (ветка) | `tests/e2e/test_heroes.py` 2 passed; `.evidence/screens/e2e-heroes-*.png` |
| 2026-10-01 | Правки после verify: типизация `body` в e2e, покрытие фронтенда (Heroes.tsx 100% строк, ветки 94%) | (ветка) | `just verify` зелёный: tree `9d9f1b8aca44`, evidence `.evidence/9d9f1b8aca449a933788bf36860f8e21b1dd2ed7.json` |

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- agent_run падал «no-progress x2» на незакрытом фронтенде — продолжено вручную; фактически бэкенд уже был в `47847f8`, оставались тесты и планка покрытия.
- Ratchet фронтенда упал на новом `Heroes.tsx` (ветки 77.9%) — закрыто тестами обликов (черепаха/кит/сова), стадии 5, отдыха, открытки, смены выбора и `POST /api/companion/seen`: строки 95.29% ≥ 94.85%, ветки 88.9% ≥ 88.15%.

## Затраты
Сессии: 2 · ≈$4.00 (agent_run ≈$3.99 + ручная догонка) · время ~1ч