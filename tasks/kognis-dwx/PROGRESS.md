# PROGRESS kognis-dwx

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Записать ответ reviewer в `tasks/kognis-dwx/REVIEW.md` (шаблон docs/templates/REVIEW.md), устранить blocker/major,
повторить ревью до `VERDICT: approve`, затем `python3 scripts/task.py done kognis-dwx`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | App.tsx → pages/ (Auth, Home, DayReview, Analysis, Quests, Profile, home/*) + components/; api.ts — типы из api.gen.ts через Refine; тесты ветвлений `pages.test.tsx`; приёмочные AC1/AC2 в `tests/web/test_frontend_structure.py`; планка фронтенда: ветвления 80.75 % | c34bbee | `just verify` OK (tree 14d59901a41a), `just e2e` 21 passed |

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- Заметка вне задачи: после «Выйти» в jsdom-тесте форма входа не появляется (client.clear() + invalidateQueries); в e2e не проверялось — при желании отдельная задача `bd`.
- Envelope в privateCrypto.ts переведён из interface в type: иначе несовместим с Record<string, unknown> из схемы.

## Затраты
Сессии: 1 · $~2.5 · время —
