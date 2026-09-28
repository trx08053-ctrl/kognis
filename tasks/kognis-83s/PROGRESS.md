# PROGRESS kognis-83s

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Устранить blocker/major из ревью (subagent `reviewer`), если есть; затем `python3 scripts/task.py done kognis-83s`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | diary: AES-GCM + argon2id, миграция 0008, `open/lock/unlock`, API web; AC1–AC3 (`tests/web/test_locked.py`) | e73a421 | verify OK, tree b9b68039db71 |
| 2026-09-29 | frontend: замок при создании, ввод пароля; e2e + axe + скриншот `.evidence/screens/e2e-locked.png` (AC4) | 0841876 | verify OK, tree 1a0cc6436ff9 |
| 2026-09-29 | docs: RUNBOOK (ключ данных), TD-8 | см. git log | — |

## Блокеры и вопросы человеку
- Конфиги развёртывания не передают `KOGNIS_DATA_KEY` (TD-8) — решение человека.

## Попытки и гипотезы (что пробовали и почему не сработало)
- Lint PLR0913 (6 аргументов) при добавлении `lock_password` — решено `EntryDraft` и `create_locked_entry`.

## Затраты
Сессии: 1 · ~$1.7
