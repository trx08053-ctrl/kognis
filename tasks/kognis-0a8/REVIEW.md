# REVIEW kognis-0a8

Ревью subagent reviewer, tree 92a4452838f1. Blocker: нет.

MAJOR: AC4 не покрывает `_achievements.py` (скрипт мутаций его не мутирует) — записано в docs/TECH_DEBT.md (TD-11).

MINOR: выжившие мутанты `has_event` — скорее эквивалентные (идемпотентность держит уникальный ключ
`uq_xp_events_owner_kind_ref`); потолок 60 XP/день при гонке — TD-11; пустая запись с отметками даёт до 25 XP
(решение TASK, на подтверждение человеку); downgrade 0017 удаляет все строки `consistency_1/2`; пустые
title/description у новых кодов в `achievement_def`; ADR 0006 — принять человеку.

NOT CHECKED: вывод mutate, фронтенд-тесты/a11y, миграция на PostgreSQL, сверка docs/modules/gameplay.md.

VERDICT: approve
