# PROGRESS kognis-2zb

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
`just task-done kognis-2zb` (перепрогонит verify сам; REVIEW.md approve, AC1–AC4 зелёные). Затем —
решение человека: `just land` ветки `feat/kognis-2zb`; при слиянии с `task/kognis-crn` возможны точечные
конфликты в `Shell.tsx`/`ProfilePage.tsx` (проверить `just integrate`).

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-10-06 | 1. Компактная шапка (логотип + чип уровня/серии + меню аватара: email/тема/выход), полоска опыта — в блоке достижений «Профиля» (`ProgressMeter`), ключ `shell.menu`; vitest обновлены под новые места элементов | f09e8aa | `just fe-check` зелёный (Biome, tsc strict, vitest, сборка) |
| 2026-10-06 | 2. e2e: хелперы `expect_signed_in`/`open_theme_toggle`/`api_xp`, обновлены `test_ui.py`, `test_logo_nav.py`, `test_landing.py`, `test_paging.py`, `test_analysis_history.py`; новый `tests/e2e/test_topbar.py` — приёмочные AC1–AC4 (`acceptance("kognis-2zb", …)`) | 83d2a54 | `just e2e` — 37 passed |
| 2026-10-06 | 3. Скриншоты (светлая/тёмная, десктоп/375px, открытое меню) просмотрены глазами; `userMenu.test.tsx` на ветки меню (покрытие/ratchet); AC1 усилен обходом разделов; ревью approve | 5cb8f02 + | `just verify` OK · tree 1a3066e30db3 · head 83d2a5457adc; e2e topbar 4 passed |

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
