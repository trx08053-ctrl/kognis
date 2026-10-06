# PROGRESS kognis-2zb

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Шаг 3 плана (TASK.md §7): скриншоты `just shot` для светлой/тёмной темы и узкого экрана (открыть PNG),
затем `just verify`, ревью subagent `reviewer` → `tasks/kognis-2zb/REVIEW.md`, `just task-done kognis-2zb`.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-10-06 | 1. Компактная шапка (логотип + чип уровня/серии + меню аватара: email/тема/выход), полоска опыта — в блоке достижений «Профиля» (`ProgressMeter`), ключ `shell.menu`; vitest обновлены под новые места элементов | f09e8aa | `just fe-check` зелёный (Biome, tsc strict, vitest 86 тестов, сборка) |
| 2026-10-06 | 2. e2e: хелперы `expect_signed_in`/`open_theme_toggle`/`api_xp`, обновлены `test_ui.py`, `test_logo_nav.py`, `test_landing.py`, `test_paging.py`, `test_analysis_history.py`; новый `tests/e2e/test_topbar.py` — приёмочные AC1–AC4 (`acceptance("kognis-2zb", …)`) | (см. git) | `just e2e` — 37 passed; `just check lint types` — ok |

## Блокеры и вопросы человеку
-

## Попытки и гипотезы (что пробовали и почему не сработало)
- `role="menu"`/`role="menuitem"` в меню аватара: перекрывают роль `button`, ломают существующие
  `getByRole("button", …)`; Biome требует `<fieldset>` для `role="group"`. Итог — disclosure-паттерн:
  кнопка с `aria-expanded`, панель с обычными кнопками; меню закрывается по Escape (фокус на аватар)
  и клику вне.
- AC2 «Выйти»: после logout интерфейс остаётся в дневнике до перезагрузки — известный баг kognis-zxb
  (вне области задачи, не исправлялся). В приёмочном тесте сессия проверяется по `/api/me` → 401.

## Затраты
Сессии: 1 · $__ · время __
