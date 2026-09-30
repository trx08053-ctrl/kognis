# PROGRESS kognis-149

## Сделано
- Сессия 1 прервана SIGTERM; wip-правка закоммитована техответственным: промпт с образцом и повтор с ошибками в `analysis/_app.py`, `_domain.py`, тесты AC1–AC4, `scripts/ai_eval.py`.
- Сессия 2: wip проверена против AC1–AC4 (тесты AC1–AC4 в `tests/analysis/test_analysis.py` зелёные); исправлены типы в тесте (basedpyright); ветка перебазирована на main (`just sync-main`).
- Доказательство: `just check types` ok; `just check tests` — 366 passed; в verify все проверки ok, кроме ratchet.

## Блокер (нужен человек)
`ratchet` падает из-за покрытия фронтенда, не связанного с задачей: `frontend/` в ветке идентичен main (`git diff main -- frontend` пуст), но vitest даёт lines 92.8 % < планка 93.1 %, branches 81.69 % < 83.38 % (планка в `.quality-baseline.json`). Похоже, планка на main выше, чем воспроизводится (лендинг kognis-6sk), либо покрытие нестабильно. Планку менять нельзя (защищённый файл) — решение человека: перепроверить планку на main или добавить тесты фронтенда отдельной задачей.
Гипотезы: (1) планка на main завышена или недетерминирована; (2) часть тестов лендинга ведёт себя иначе в этой среде.
Один прогон sync-main показал ещё и FAIL tests; повтор `just check tests` прошёл (366 passed) — вероятно флейк.

## Следующий шаг
После решения по планке фронтенда: `just verify`, ревью subagent `reviewer` → `tasks/kognis-149/REVIEW.md`, `just task-done kognis-149`.
