# REVIEW kognis-3fl

## Ревью 1 (subagent reviewer)
VERDICT: request-changes

- **major:** рецепта `just ai-eval` нет — `justfile` защищён; AC1 в формулировке TASK не выполнен. **Не устранено агентом:** нужно решение человека
  (добавить рецепт `ai-eval *args:` → `uv run --locked python scripts/ai_eval.py {{args}}` либо поправить AC1). Задача заблокирована `needs_input`.
- **major:** R3 не снимается — реальный прогон (AC4) за техответственным; записано в PROGRESS.md «Следующий шаг». Учтено.
- **blocker (доказательство):** свежий `just verify` — выполнен на коммите f090fec: verify OK · tree 7f5eca2534b0.
- minor: `.tmp_r.jsonl` — удалён, в git не попадал. Команда в README/docstring `python3 scripts/ai_eval.py` требует venv — использовать
  `uv run --locked python scripts/ai_eval.py` (не исправлено автоматически, мелкая правка документации). Список `FORBIDDEN` эвристический — расширить после реального прогона.

Не проверено ревьюером: diff, запуск тестов, 9 из 11 файлов cases, поведение на реальной модели.
