# REVIEW kognis-e7s — итог ревью

## Ревью 1 · 2026-09-29 · 9518f24
```
VERDICT: request-changes
EVIDENCE: NOT verified (у reviewer не было Bash; .evidence — состояние до коммита)
BLOCKERS: нет
MAJOR: docs/modules/web.md — карточка модуля устарела (/health с БД, docs только в dev, схема из create_app().openapi(), правило 404 в SPA-заглушке)
MINOR:
- _app.py: except Exception в /health без лога — оператор не увидит причину
- /health без своего таймаута подключения (приемлемо: HEALTHCHECK timeout=3s)
- "docs/" со слэшем уходит в SPA index.html, не 404 (безвредно)
- тест: проверка "missing" not in text избыточна
- тест AC3: regex ловит pg_dump только в одной строке с docker compose
NOT CHECKED: just contract/api-types, just stage на реальном PostgreSQL, check_scope, работоспособность команд RUNBOOK
```

## Устранено
| Замечание | Что сделано | Коммит / тест |
|---|---|---|
| MAJOR карточка web | добавлен пункт «Эксплуатация» в docs/modules/web.md | 9c117ab |
| лог 503 | логируется только имя класса исключения, без параметров | 9c117ab |
| тест AC3 | добавлены проверки отсутствия pg_dump/pg_restore в RUNBOOK | 9c117ab |
| таймаут, "docs/", избыточная проверка | не менялось: приемлемо / безвредно (обоснование выше) | — |
| NOT CHECKED: contract | `just verify` (contract ok, tree 6eb1878fdebf) | evidence 6eb1878f… |
