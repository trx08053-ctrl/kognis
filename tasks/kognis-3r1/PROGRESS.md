# PROGRESS kognis-3r1

## Сделано
- Шаг 1 (бэкенд + интерфейс, единым блоком — они связаны типами API): TASK.md, ADR 0006 (Proposed — принять человеку), метрики в ARCHITECTURE §6, миграция 0016 (`gameplay_settings`, `streak_recoveries`; существующим пользователям `rules_from` = дата миграции), модель серии `src/kognis/gameplay/_streak.py` (запас заморозок, выходные, восстановление 72 ч, недельная цель), `PUT /api/progress/settings`, `POST /api/progress/recovery`, расширенный `GET /api/progress`, панель «Ваш путь» в профиле (`components/Motivation.tsx`), шапка без «Серия: 0», словари ru.
- Тесты: `tests/gameplay/test_streak_model.py` (AC1, hypothesis), `tests/web/test_motivation.py` (AC2), `frontend/src/motivation.test.tsx` через `tests/web/test_motivation_frontend.py` (AC3), `tests/gameplay/test_migration_0016.py` (AC4).
- Изменены существующие тесты (правило заменено задачей, не ослабление): `tests/web/test_gameplay.py` — `test_new_user_starts_at_level_one` получил новые поля ответа; `test_one_freeze_per_week_bridges_single_missed_day` → `test_freeze_stock_bridges_missed_days_until_it_runs_out` (одна заморозка на ISO-неделю заменена запасом). `test_domain.py` / `test_mutants.py` (прежняя `streak_length`) не тронуты — функция осталась эталоном для переходного периода.

## Не сделано / для человека
- Скриншот экрана (AC3 упоминает «скриншот») — `just shot` не запускался (нужен поднятый сервер и браузер); компонентный тест есть.
- ADR 0006 принять; метрики удержания измеряются после выпуска.
- Герои, баланс XP, достижения по уровням — задачи kognis-0a8 и далее.

- Ревью: раунд 1 — major (гонка бонуса недели) устранён в b82547c, раунд 2 — `VERDICT: approve` (`REVIEW.md`). `just verify` зелёный (покрытие добрано тестами гонок в `tests/gameplay/test_service.py`).

## Следующий шаг
`python3 scripts/task.py done kognis-3r1`; человеку — принять ADR 0006.
