"""Правила игровой механики: чистые функции модуля gameplay."""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from kognis.gameplay import ACHIEVEMENTS
from kognis.gameplay._domain import (
    earned_achievements,
    level_for,
    level_start,
    streak_length,
)

DAY = date(2026, 9, 7)  # понедельник


@given(st.integers(min_value=0, max_value=100_000))
def test_level_matches_its_start_thresholds(xp: int) -> None:
    level = level_for(xp)
    assert level_start(level) <= xp < level_start(level + 1)


@given(st.integers(min_value=0, max_value=5_000), st.integers(min_value=0, max_value=5_000))
def test_level_never_decreases_with_xp(a: int, b: int) -> None:
    low, high = sorted((a, b))
    assert level_for(low) <= level_for(high)


def test_streak_of_consecutive_days() -> None:
    days = [DAY + timedelta(days=i) for i in range(5)]
    assert streak_length(days, days[-1]) == 5
    assert streak_length([], DAY) == 0
    assert streak_length(days, days[-1] + timedelta(days=1)) == 5


def test_second_missed_day_in_same_week_breaks_streak() -> None:
    # пн, (вт), ср, (чт), пт — вторая заморозка в неделе недоступна
    days = [DAY, DAY + timedelta(days=2), DAY + timedelta(days=4)]
    assert streak_length(days, days[-1]) == 1


def test_pending_freeze_keeps_streak_alive_for_one_more_day() -> None:
    days = [DAY, DAY + timedelta(days=1)]
    assert streak_length(days, DAY + timedelta(days=3)) == 2  # пропущен один день — заморозка
    assert streak_length(days, DAY + timedelta(days=4)) == 0


def test_future_days_are_ignored() -> None:
    assert streak_length([DAY + timedelta(days=5)], DAY) == 0


def test_achievements_only_new_ones() -> None:
    got = earned_achievements(entries=1, reviews=10, streak=7, already=["first_entry"])
    assert got == ["streak_3", "streak_7", "reviews_10"]
    assert set(got) <= {a.code for a in ACHIEVEMENTS}
