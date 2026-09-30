# PROGRESS kognis-sky

## Сделано
- Шаг 1 (бэкенд): TASK.md, ADR 0005 (Proposed — принять человеку), миграция 0015 `analysis_memory`, лимит периода 31 день, бюджет текста (`fit_texts`), период по умолчанию (`GET /api/analyses/period`), 409 `analysis.duplicate` (после кризисной проверки), память (`GET|DELETE /api/analyses/memory`), `changes`/`memory` в ответе модели, карточка модуля. Тесты: `tests/analysis/test_continuity.py` (AC1–AC5). Старые тесты адаптированы к дублям (другой конец периода) и лимиту 31.
- Доказательство: `just verify` OK, tree 2c7d13a3016a.

## Следующий шаг
Шаг 2 (фронтенд): на `AnalysisPage` — период по умолчанию из `/api/analyses/period` (неактивная кнопка + подсказка «новых записей нет» + ссылка на последний разбор, пояснение при `truncated`), обработка 409 (открыть существующий), блок «Что изменилось», «Что ИИ помнит обо мне» + «Очистить память»; vitest `frontend/src/analysisContinuity.test.tsx` через `tests/web/` (AC6). Затем шаг 3: пример ai-eval с памятью, ревью `reviewer`, `python3 scripts/task.py done kognis-sky`.
