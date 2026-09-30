# PROGRESS kognis-sky

## Сделано
- Шаг 1 (бэкенд): TASK.md, ADR 0005 (Proposed — принять человеку), миграция 0015 `analysis_memory`, лимит периода 31 день, бюджет текста (`fit_texts`), период по умолчанию (`GET /api/analyses/period`), 409 `analysis.duplicate` (после кризисной проверки), память (`GET|DELETE /api/analyses/memory`), `changes`/`memory` в ответе модели, карточка модуля. Тесты: `tests/analysis/test_continuity.py` (AC1–AC5). Старые тесты адаптированы к дублям и лимиту 31. Коммит dd9b37f.
- Шаг 2 (фронтенд): период по умолчанию из сервера (неактивная кнопка + «новых записей нет» + ссылка на последний разбор, пояснение при усечении до 31 дня), 409 → «Открыть существующий разбор», блок «Что изменилось», «Что ИИ помнит обо мне» + «Очистить память»; история вынесена в `pages/analysis/AnalysisHistory.tsx` (лимит 500 строк). Vitest `analysisContinuity.test.tsx` через `tests/web/test_analysis_continuity_frontend.py` (AC6). e2e кризисного разбора: после разбора «сегодня» период выбирается вручную.
- Доказательство: `just verify` OK, tree 4ab972b4c98c.

## Не сделано (нужен человек)
- Пункт 7 постановки — ai-eval пример с предыдущей памятью: требует правки `scripts/ai_eval.py` (защищённый каталог) — вынесено отдельной задачей bd; прогон на реальной модели и принятие ADR 0005 — техответственный.

## Ревью и состояние
- Коммит 89d9042: IDOR памяти ИИ (`tests/security/test_idor.py`), ревью `tasks/kognis-sky/REVIEW.md` — VERDICT: approve (blocker нет, major устранены).
- Evidence: `.evidence/4c7f8b32fa04975e18b1f41d4fa768652cdbfdbc.json` (verified).
- Попытка `python3 scripts/task.py done kognis-sky` дважды отклонена запросом подтверждения (автономный режим, человека нет) — задача не закрыта.

## Следующий шаг
Человек (или сессия с разрешением) выполняет `python3 scripts/task.py done kognis-sky` (перезапустит verify). Затем: принять ADR 0005, прогнать память/«Что изменилось» на реальной модели, решить про TECH_DEBT (гонка `set_memory`); ai-eval — задача kognis-bgo.
