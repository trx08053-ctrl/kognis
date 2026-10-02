# PROGRESS kognis-crn

## Следующий шаг
Ревью approve (раунд 3, REVIEW.md). `just task-done kognis-crn`; далее — `just land` (перенос веток
в main) — решение человека.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-10-01 | Карта модулей (explorer): хуки начислений `_app.py:173-188`, `_quests_app.py:108-118`; заморозки вычисляются в `_streak.py` (не хранятся); `day_reviews.mood` 1–10 готов для мозаики; выборка записей `list_between` + `protection`; маршруты/IDOR-паттерны | — | вывод explorer-сабагента |
| 2026-10-01 | Ветка `task/kognis-crn` (от закрытой `task/kognis-zjg`), TASK.md + PROGRESS.md | `b8f0ed7` | разделы 1–8 TASK.md, план из 6 шагов |
| 2026-10-01 | Шаг 1: домен искр `_sparks.py` (начисления за факт, каталог-данные), журнал `spark_events`/`spark_purchases` (миграция 0019, expand), хуки в `_grant` и `complete_step`, купленные заморозки в серии (`StreakRules.bought`, кап 2) | `c0ced75` | `tests/gameplay/` + `test_gameplay.py` 84 passed; миграции ok; тест миграции 0019; `test_streak_model` с bought-сценариями |
| 2026-10-01 | Шаг 2: сервис `SparksService`, API `GET /api/sparks` + `POST /api/sparks/purchase` (409-коды, заморозка при полном запасе), advisory-лок покупок на Postgres | `517eaed` | AC1: `tests/web/test_sparks.py` 6 passed (в т.ч. конкурентность без минуса) |
| 2026-10-01 | Шаг 3: квест дня `_daily.py` (пул 9, детерминированный выбор 3), `daily_picks` (миграция 0020), API `/api/daily-quest` (выбор 1/день, выполнение), недельная рекомендация наставника, +5 искров за день, коды ошибок в словаре | `ad7fb16` | AC2: `test_daily.py` + `test_daily_quest.py` 12 passed; gameplay+web 271 passed; миграции ok |
| 2026-10-01 | Шаг 4: архив — `GET /api/archive/on-this-day` (год/месяц назад, только plain), `/api/archive/mood-year` (мозаика) | `8400517` | AC3: `tests/web/test_archive.py` 4 passed (IDOR-изоляция, без замков, окно 365 дней) |
| 2026-10-01 | Шаг 5: фронтенд — api-клиент, магазин `Sparks.tsx`, квест дня `DailyQuest.tsx`, `ArchivePage` (мозаика Year-in-Pixels), аксессуары в SVG, маршрут `/archive`, словари | `844d462` | vitest 112 passed; tsc/biome чистые; ветки 89.84% ≥ планки |
| 2026-10-01 | Шаг 6: e2e AC4 — покупка шарфа меняет облик спутника, скриншот + axe без serious/critical | `581cb64` | `just e2e -k accessory`: 1 passed; `.evidence/screens/e2e-sparks-accessory.png` |
| 2026-10-01 | verify: планка покрытия веток и строк закрыта тестами (гонка покупок, advisory-лок в Postgres-интеграции, error-пути), карточка модуля и MAP обновлены | `4ba0bc1` | `just verify` зелёный: tree `fe218d5f4845`, evidence `.evidence/fe218d5f484528854e66f8bb325454ca190d1d0e.json` |

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- `streak_3` (старый код) получал 50 искр «как золото» по суффиксу `_3` — исправлено: уровень только у новых кодов `<категория>_<уровень>`, старые — как бронза.
- Тесты миграций 0016–0018 поймали: `freeze_days` в `_state` падал на схеме до 0019 — добавлен expand-fallback (таблицы нет → покупок нет), иначе новый код ломал бы существующие маршруты до наката миграции.

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
-

## Затраты
Сессии: 2 · ≈$3.7 (карта модулей ~$0.6, закрытие zjg ранее) · время ~1.5ч