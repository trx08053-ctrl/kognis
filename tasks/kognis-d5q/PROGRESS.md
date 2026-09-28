# PROGRESS kognis-d5q

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Устранить blocker/major из ревью (reviewer), затем `just verify` и `python3 scripts/task.py done kognis-d5q`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | safety: детектор RU/EN, контакты (112, `KOGNIS_HELP_CONTACTS`), `allows_rewards`; diary `crisis` + миграция 0004; web возвращает `crisis`/`help` (AC1–AC3) | 667c70a | verify OK, tree 5f54a2619eca |
| 2026-09-29 | frontend: блок помощи (role=alert, tel:), дисклеймер; vitest + e2e с axe, скриншот `.evidence/screens/e2e-crisis-help.png` осмотрен | 4f46e9a | verify OK, tree 562a9261c734 |

## Блокеры и вопросы человеку
- Владельцу: проверить и дополнить список горячих линий (`KOGNIS_HELP_CONTACTS`), по умолчанию только 112 (D5).
- Вне области задачи: сигнал в «рефлексии» итога дня не проверяется; XP/квесты/анализ применят `allows_rewards` в задачах gameplay/analysis.
- В рабочей копии есть чужая правка `tasks/kognis-0wr/TASK.md` — не коммитилась.

## Попытки и гипотезы (что пробовали и почему не сработало)
- `create_entry(..., crisis=...)` упирался в ruff PLR0913 (>5 аргументов) — сделан отдельный `DiaryService.mark_crisis`.

## Затраты
Сессии: 1 · $~1 · время ~30 мин
