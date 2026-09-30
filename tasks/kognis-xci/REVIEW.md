# REVIEW kognis-xci

Ревью 1 (reviewer, ec4980a): blocker — нет; major — карточка `docs/modules/analysis.md` не отражала выключенный детектор и страховку в промпте; minor — оговорка про fake в evals README, тест off для квиза.
Устранено: карточка analysis обновлена, оговорка добавлена, тест `test_crisis_phrase_in_quiz_is_ordinary_when_detector_off`.
Не проверено: качество совета реальной модели (`just ai-eval --provider env`) — техответственный; off для follow-up-ответов отдельным тестом не покрыт (тот же `_crisis_block` → `check_text`).
Minor принято как есть: широкий список слов `SUPPORT_ADVICE` — задан постановкой задачи.

VERDICT: approve
