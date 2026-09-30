# PROGRESS kognis-xci

## Сделано
- Сессия 1: TASK.md; `KOGNIS_CRISIS_DETECTOR` (off по умолчанию) в `safety`; страховка в промпте (`analysis/_prompts_i18n.py`);
  тексты лендинга без обещания распознавания кризиса; `scripts/ai_eval.py` — grounding по всем данным, проверка
  `support_advice` при off; документация (RUNBOOK, ARCHITECTURE R4, карточка safety, evals/ai/README); задача kognis-fvn.
- Тесты AC1–AC6 (`tests/analysis/test_crisis_detector_off.py`, `tests/e2e/test_landing.py`, `tests/ai/test_ai_eval.py`);
  существующие кризисные тесты переведены на явный `crisis_on`.
- Доказательство: `just verify` зелёный, tree d1ee5666b031.

## Следующий шаг
Ревью 1: approve после правок (REVIEW.md), verify зелёный, tree acbfd23b44e7. Осталось: `python3 scripts/task.py done kognis-xci`.
Реальный прогон `just ai-eval --provider env --direction all` (support_advice на модели) — техответственный.
