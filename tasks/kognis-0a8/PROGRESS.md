# PROGRESS kognis-0a8

## Сделано
- Шаг 1–2 (бэкенд + интерфейс единым блоком, связаны типами API), коммит acd3a5e: TASK.md; правила XP как данные
  (`_domain.py`: запись 10 ≤ 3/день, итог дня 15, ответ разбора 10, бонус рефлексии 5–15 по отметкам
  пользователя, потолок 60 XP/день); каталог достижений `_achievements.py` (4 категории × 3 уровня + скрытые
  `comeback`, `first_gratitude`, `year_diary`); миграция 0017 (`xp_events.marks`, соответствие
  `streak_7/30` → «Постоянство»); `GET /api/progress` + `categories`, `hidden`; поле `marks` в записи и итоге
  дня; начисление за ответ на вопросы разбора и учёт направлений (`reward_analysis`); квесты/квизы выдают
  достижения сразу (`GameplayService.refresh`); интерфейс: `MarksField`, сетка достижений; словари ru.
- Тесты: `tests/gameplay/test_xp_balance.py` (AC1, hypothesis), `tests/web/test_achievements.py` и
  `test_achievements_frontend.py` (AC2), `tests/gameplay/test_migration_0017.py` (AC3).
- Изменены существующие тесты (правило заменено задачей, не ослабление): итог дня 20 → 15
  (`test_gameplay.py`, `test_crisis_review.py`), ответ `/api/progress` получил `categories`/`hidden`,
  `test_migration_0016.py` поднимается до `head` вместо `0016` (сервис теперь требует колонку `marks`),
  фикстуры прогресса во фронтенд-тестах дополнены новыми полями.
- Мутации (`just mutate kognis-0a8`, AC4): порог 80% пройден. Выжили мутанты на аргументах `has_event`
  (идемпотентность начислений по owner/kind/ref) — кандидат на доп. тест отдельной задачей.
- `just map` → docs/MAP.md, `just verify` OK, tree 92a4452838f1,
  evidence `.evidence/92a4452838f18f834da9c75fcd13ba479574ea94.json`.

## Не сделано / для человека
- Достижения «Исследователя» у существующих пользователей начинаются с нуля: прошлые разборы по направлениям
  не пересчитаны (миграция переносит только серии) — при желании отдельная задача.
- Скриншот экрана достижений (`just shot`) не снимался; компонентные тесты есть.
- Мутационная проверка не покрывает `_achievements.py` (скрипт мутирует только `_domain.py`/`_app.py`).
- ADR 0006 (Proposed) — принять человеку.

## Следующий шаг
Ревью reviewer запущено (результат → `tasks/kognis-0a8/REVIEW.md`). Если VERDICT: approve — `python3
scripts/task.py done kognis-0a8`; blocker/major — устранить, `just verify`, повторить ревью.
