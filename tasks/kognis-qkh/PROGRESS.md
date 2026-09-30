# PROGRESS kognis-qkh

## Сделано
- Шаг 1 (бэкенд): `GET /api/analyses?limit&offset` (новые сверху, следующее смещение — `X-Next-Cursor`), `created_at` в `AnalysisOut`, `DELETE /api/analyses/{id}` (JSON-тело обязательно — правило CSRF). Тесты: `tests/analysis/test_history.py`, idor в `tests/security/test_idor.py` (AC2 API, AC4).
- Доказательство: `just verify` OK, tree 5de48bf28838.

## Следующий шаг
Шаг 2: фронтенд — список разборов на `AnalysisPage` (useInfiniteQuery, «Показать ещё», последний открыт по умолчанию), открытие, удаление, показ `answers`; новый текст через `t()`; vitest `frontend/src/analysisHistory.test.tsx` (AC2, AC3). Затем шаг 3: e2e `tests/e2e/test_analysis_history.py` (AC1).
