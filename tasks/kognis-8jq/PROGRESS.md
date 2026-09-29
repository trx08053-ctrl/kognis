# PROGRESS kognis-8jq

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Ревью (reviewer): approve, blocker/major нет. Выполнить `python3 scripts/task.py done kognis-8jq`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | Тесты AC1–AC3 (gameplay, diary); `level_for`/`level_start` без ветвления (поведение то же) | bc5899b | verify OK · tree 3f937cc225be; `just mutate kognis-50k` 240/240, `kognis-7cn` 38/38 |

## Разбор выживших мутантов
- kognis-50k (12): защита от повторного начисления (owner/kind/ref) и `achievements(owner)` — `test_award_is_once_per_owner_and_entry_but_independent_across_them`, `test_repeated_award_does_not_retry_granted_achievements`; неделя заморозки (`idle <= 2`, `days[-1]+1`) — `test_level_thresholds_and_freeze_week_boundaries`.
- Мутанты порога уровня (`extra >= 0`, `level <= len`) были эквивалентны (на границе обе ветки дают одно значение). Pragma не ставил (новые подавления требуют человека) — функции переписаны без ветвления, эквивалентов не осталось.
- kognis-7cn (9): границы оценок 1/10 и 0/11, длина рефлексии 5000/5001, точные тексты ошибок — `tests/diary/test_boundaries.py`.
- Ошибок в коде тесты не выявили.

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- `pragma: no mutate` для эквивалентных мутантов → ratchet отклонил как новое подавление; заменено рефакторингом.

## Затраты
Сессии: 1 · $~0.7 · время ~30 мин
