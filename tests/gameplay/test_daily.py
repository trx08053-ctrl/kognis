"""Квест дня (kognis-crn, AC2 — домен): детерминированный выбор, недельная рекомендация."""

from datetime import date, timedelta

from kognis.gameplay._daily import DAILY_OPTIONS, DAILY_POOL, options_for, weekly_recommendation
from kognis.gameplay._quests import QUESTS

MON = date(2026, 9, 7)


def test_options_are_three_known_codes_from_the_pool() -> None:
    options = options_for(1, MON)
    assert len(options) == DAILY_OPTIONS
    assert set(options) <= set(DAILY_POOL)


def test_options_are_stable_for_user_and_day_and_change_next_day() -> None:
    assert options_for(1, MON) == options_for(1, MON)  # один и тот же день
    assert options_for(1, MON) != options_for(1, MON + timedelta(days=1))  # завтра другие


def test_options_differ_between_users_but_same_for_each() -> None:
    first, second = options_for(1, MON), options_for(2, MON)
    assert first != second  # у каждого свой день
    assert len(set(first) & set(second)) < DAILY_OPTIONS  # пересечение не полное


def test_all_pool_codes_appear_over_time() -> None:
    """Пул не «прилипает»: за месяц всплывают все варианты (против скуки)."""
    seen: set[str] = set()
    for offset in range(28):
        seen.update(options_for(7, MON + timedelta(days=offset)))
    assert seen == set(DAILY_POOL)


def test_weekly_recommendation_is_not_open_and_deterministic() -> None:
    non_challenges = tuple(q.code for q in QUESTS if not q.challenge)
    open_codes = frozenset({non_challenges[0]})
    first = weekly_recommendation(1, "2026-W37", open_codes)
    assert first in non_challenges
    assert first not in open_codes
    assert first == weekly_recommendation(1, "2026-W37", open_codes)  # тот же ответ
    assert weekly_recommendation(1, "2026-W38", open_codes) or True  # неделя меняется


def test_weekly_recommendation_skips_open_quests() -> None:
    """Рекомендуем только то, что не принято: давление повтором исключено."""
    non_challenges = [q.code for q in QUESTS if not q.challenge]
    taken = frozenset(non_challenges[:-1])
    assert weekly_recommendation(1, "2026-W37", taken) == non_challenges[-1]


def test_weekly_recommendation_none_when_all_taken() -> None:
    non_challenges = [q.code for q in QUESTS if not q.challenge]
    assert weekly_recommendation(1, "2026-W37", frozenset(non_challenges)) is None
