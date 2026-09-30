# REVIEW kognis-3r1

## Раунд 1 (b7d9101)
- MAJOR: гонка бонуса недели (`add_event` без savepoint → 500 и откат записи дневника) — исправлено: `add_event_once` (savepoint + `IntegrityError`), тест в `tests/gameplay/test_service.py`.
- MINOR: заметка из пробелов → исправлено (`pattern=r"\S"`, тест); гонка первого PUT settings → исправлено (savepoint + update).
- MINOR: `recoverable_break` до `rules_from` предлагает бесполезное восстановление — не блокер, заведена задача bd.
- MINOR: в TASK 2a вместо `Progress.tsx` — `Motivation.tsx` — строка исправлена.
- ADR 0006 остаётся Proposed — принять человеку; замена правила «одна заморозка на неделю» запасом заложена задачей.

## Раунд 2 (b82547c)
BLOCKERS: нет. MAJOR: нет.
Не проверено: поведение savepoint под настоящей конкуренцией на Postgres; `Motivation.tsx` и тон текстов; скриншот (`just shot`).

VERDICT: approve
