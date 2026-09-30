# PROGRESS kognis-qkh

## Сделано
- Шаг 1 (бэкенд): `GET /api/analyses?limit&offset` (новые сверху, следующее смещение — `X-Next-Cursor`), `created_at` в `AnalysisOut`, `DELETE /api/analyses/{id}` (JSON-тело обязательно — правило CSRF). Тесты: `tests/analysis/test_history.py` (AC2, AC3, AC4), idor в `tests/security/test_idor.py` (AC4).
- Шаг 2 (фронтенд): на `AnalysisPage` — постраничный список («Показать ещё»), последний разбор открыт по умолчанию, открытие любого, удаление с подтверждением, блок «Ваши ответы»; новый текст — через `t()`. Vitest `frontend/src/analysisHistory.test.tsx` через `tests/web/test_analysis_history_frontend.py` (AC2, AC3).
- Шаг 3: e2e `tests/e2e/test_analysis_history.py` (AC1: запуск → уход → возврат → перезагрузка → удаление).
- Доказательство: `just verify` OK, tree 895b621d6a9d.
- Известное ограничение: кризисный разбор из истории показывает только пояснение без контактов помощи (сервер их не хранит; блок помощи приходит только сразу после запуска).

## Следующий шаг
Ревью subagent `reviewer` → `tasks/kognis-qkh/REVIEW.md`, устранить blocker/major, затем `python3 scripts/task.py done kognis-qkh`.
