# REVIEW kognis-2zb — итог ревью (обязателен для standard и risky; `task-done` без него не закроет)

Ответ subagent `reviewer` — как есть, затем что сделано по каждому замечанию. Последнее ревью — внизу.

## Ревью 1 · 2026-10-06 · 5cb8f02
```
VERDICT: approve
EVIDENCE: verified tree 1a3066e30db3f88826c2332b3d75f7a87e1c00cc (evidence .evidence/1a3066e30db3….json, ok:true;
tests: 529 passed; все проверки exit 0, включая frontend, tests, i18n, no-weakening, arch-doc, docs).
BLOCKERS: нет. Ослабления проверок нет: no-weakening ok; конфиги проверок (pyproject/justfile/lefthook/
.quality-baseline.json/scripts/.claude) diff не трогает.
MAJOR: нет.
MINOR:
  - tests/e2e/test_ui.py:421,434,447 — в test_quests_screen UI-проверка «Опыт: N из 50» заменена на api_xp
    (опрос /api/progress): проверка начисления опыта сохранена, но проверка отрисовки на этом экране снята.
  - tests/e2e/test_topbar.py:64-66 — AC1: отсутствие progress/xp проверялось только на дневнике, не во всех
    разделах («нет ни в одном разделе, кроме Профиля»).
  - frontend/src/App.test.tsx:281-286 — из фикстуры PROGRESS убраны best_streak/week_days: заголовок их не
    использует, но фикстура менее полная.
  - frontend/src/components/Shell.tsx:121 — flex-wrap: на узком экране «одна строка» переносится в две
    (см. tm0-day-mobile-light.png) — разумный отклик, но отклонение от буквы AC.
NOT CHECKED: RTL (единственная локаль ru; end-0 логическое свойство — не проверено глазами); отдельный
скриншот меню аватара в тёмной теме; aria-haspopup на аватаре (axe зелёный и без него); бэкенд/gameplay
(задача presentational).
```
Примечание ревьюера: у каждого AC — ровно один `@pytest.mark.acceptance("kognis-2zb", "ACn")` в
`tests/e2e/test_topbar.py`; UserMenu корректен (aria-expanded, Escape с возвратом фокуса, закрытие по
mousedown вне, слушатели только пока меню открыто); ProgressWidget удалён без висячих импортов; новый ключ
`shell.menu` есть в словаре; email — текстовый узел JSX (XSS-поверхности нет).

## Устранено
| Замечание | Что сделано | Коммит / тест |
|---|---|---|
| MINOR: AC1 — отсутствие опыта только на дневнике | Принято: в AC1 добавлен обход разделов «Дневник / Итог дня / Разбор / Квесты» с проверкой `xp`/`progress` = 0 | `test_topbar.py` AC1 |
| MINOR: UI→API в test_quests_screen | Принято без изменений: элемента xp на этих экранах больше нет; отрисовка покрыта AC3 (`test_topbar.py`) и `test_progress_widget_and_achievements_page` (kognis-50k). Полноценный дожид через `api_xp` сохраняет строгость чисел | `tests/e2e/test_ui.py` |
| MINOR: фикстура без best_streak/week_days | Принято: `App.test.tsx` упёрся в лимит `test_no_frontend_file_is_too_long` (500 строк); убраны только непроверяемые поля, assert-ы не тронуты | `frontend/src/App.test.tsx` |
| MINOR: перенос строки на узком экране | Принято: `flex-wrap` — намеренный отклик (одна компактная строка-блок вместо двух блоков, на 375px — без горизонтальной прокрутки); см. `.evidence/screens/tm0-home-mobile-*.png` | — |
