# PROGRESS kognis-1gr

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Дождаться результата subagent `reviewer` по коммиту 9037c47 (если сессия прервалась — запустить его заново), устранить blocker/major, затем `just verify` и `python3 scripts/task.py done kognis-1gr`. Также в рабочей копии есть незакоммиченный `.quality-baseline.json` (планка покрытия после `just ratchet-up`; защищённый файл, hook не дал агенту его закоммитить) — при необходимости оставить человеку.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | Модуль ai: `AiProvider`, `FakeProvider`, `OpenAICompatibleProvider` (повтор 429/5xx, таймаут, без утечки ключа), `get_provider` по env; тесты AC1–AC3 (`tests/ai/test_ai.py`); карточка `docs/modules/ai.md` | 9037c47 | `just verify` OK · tree 7030f58e355d · evidence `.evidence/7030f58e355deb48ef8090493a424361fba2711b.json` |

## Блокеры и вопросы человеку
- `.quality-baseline.json` изменён `just ratchet-up` (покрытие 98.17% → 98.78%), не закоммичен.

## Попытки и гипотезы (что пробовали и почему не сработало)
- verify падал на lint (PLR0913, PLR2004), `pragma: no cover` без обоснования и устаревшей MAP — исправлено рефакторингом (`HttpSettings`, `response.is_success`, цикл без недостижимой ветки), `just map`.

## Затраты
Сессии: 1 · $~0.6 · время —
