"""Модель серии «Нить» (kognis-3r1, AC1): заморозки, выходные, восстановление. Чистые функции."""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kognis.gameplay._domain import streak_length
from kognis.gameplay._streak import (
    StreakRules,
    days_with_diary,
    recoverable_break,
    streak_state,
    week_ref,
)

MON = date(2026, 9, 7)  # понедельник
NEW = StreakRules()


def d(*offsets: int) -> list[date]:
    return [MON + timedelta(days=n) for n in offsets]


def at(offset: int) -> date:
    return MON + timedelta(days=offset)


@pytest.mark.acceptance("kognis-3r1", "AC1")
def test_missed_day_is_covered_by_a_freeze_from_the_stock() -> None:
    state = streak_state(d(0, 1, 3), at(3), NEW)  # вторник пропущен, вт+1 день заморозки
    assert (state.current, state.freezes, state.breaks) == (3, 1, ())


@pytest.mark.acceptance("kognis-3r1", "AC1")
def test_each_missed_day_costs_one_freeze_and_without_stock_the_streak_breaks() -> None:
    # пропущены вт, ср — обе закрыты (запас 2), затем пропущены сб, вс — нечем
    days = d(0, 3, 6)  # пн, чт, вс
    state = streak_state(days, at(6), NEW)
    assert state.current == 1
    assert [(b.broken_on, b.streak_before) for b in state.breaks] == [(at(4), 2)]
    assert state.freezes == 0


@pytest.mark.acceptance("kognis-3r1", "AC1")
def test_weekend_days_neither_break_nor_extend_the_streak() -> None:
    weekend = StreakRules(weekend_days=frozenset({5, 6}))  # сб, вс
    state = streak_state(d(4, 7), at(7), weekend)  # пт → пн через сб и вс
    assert (state.current, state.freezes) == (2, 2)  # запас не тронут, серия только 2 дня
    assert streak_state(d(4), at(7), weekend).current == 1  # и в хвосте выходные не рвут


@pytest.mark.acceptance("kognis-3r1", "AC1")
def test_freeze_stock_is_replenished_every_seven_active_days_up_to_two() -> None:
    days = d(0, 1, 2, 3, 4, 5, 6)  # 7 активных дней: +1, но запас уже полный (2)
    assert streak_state(days, at(6), NEW).freezes == 2
    spend = d(0, 2, 3, 4, 5, 6, 7, 8)  # пропущен вт: запас 1, к 7-му активному дню снова 2
    assert streak_state(spend, at(8), NEW).freezes == 2
    assert streak_state(d(0, 2, 3), at(3), NEW).freezes == 1  # без 7 дней не пополнилось


@pytest.mark.acceptance("kognis-3r1", "AC1")
def test_recovery_is_possible_within_72_hours_and_only_once() -> None:
    days = d(0, 1, 2)
    state = streak_state(days, at(6), NEW)  # пропущены чт, пт — закрыты; сб — обрыв
    assert state.current == 0
    brk = recoverable_break(state, at(6))
    assert brk is not None
    assert (brk.streak_before, brk.broken_on) == (3, at(5))
    assert recoverable_break(state, at(8)) is not None  # 3 дня после первого пропущенного
    assert recoverable_break(state, at(9)) is None  # 72 часа прошли
    restored = streak_state(days, at(6), StreakRules(recovered=frozenset({brk.after_day})))
    assert restored.current == 3
    assert recoverable_break(restored, at(6)) is None  # один обрыв — одно восстановление


@pytest.mark.acceptance("kognis-3r1", "AC1")
def test_recovery_joins_the_old_and_the_new_streak() -> None:
    days = d(0, 1, 2, 7, 8)  # обрыв после вт, потом два дня
    plain = streak_state(days, at(8), NEW)
    assert plain.current == 2
    brk = plain.breaks[0]
    joined = streak_state(days, at(8), StreakRules(recovered=frozenset({brk.after_day})))
    assert joined.current == 5  # 3 + 2, дни обрыва серию не удлиняют
    assert joined.best == 5


def test_short_streak_is_not_offered_for_recovery() -> None:
    state = streak_state(d(0), at(5), NEW)
    assert state.breaks
    assert recoverable_break(state, at(5)) is None


def test_old_rule_before_rules_from_one_free_freeze_per_iso_week() -> None:
    legacy = StreakRules(rules_from=date(2030, 1, 1))
    for days, today in [
        (d(0, 2, 4), at(4)),
        (d(0, 1), at(3)),
        (d(0, 1), at(4)),
        (d(0, 2, 3, 4, 5), at(7)),
    ]:
        assert streak_state(days, today, legacy).current == streak_length(days, today)


def test_days_with_diary_counts_last_30_and_total() -> None:
    days = [at(0), at(-29), at(-30), at(-100)]
    assert days_with_diary(days, at(0)) == (2, 4)
    assert days_with_diary([*days, at(5)], at(0)) == (2, 4)  # будущие даты не считаются


def test_week_ref_is_iso_week() -> None:
    assert week_ref(date(2026, 1, 1)) == "2026-W01"
    assert week_ref(date(2026, 12, 31)) == "2026-W53"


DAY_OFFSETS = st.sets(st.integers(min_value=0, max_value=120), min_size=1, max_size=80)


@given(
    DAY_OFFSETS,
    st.integers(min_value=0, max_value=30),
    st.sets(st.integers(min_value=0, max_value=6), max_size=2),
)
def test_streak_never_exceeds_active_or_calendar_days(
    offsets: set[int], idle: int, weekend: set[int]
) -> None:
    days = [at(n) for n in offsets]
    today = max(days) + timedelta(days=idle)
    state = streak_state(days, today, StreakRules(weekend_days=frozenset(weekend)))
    calendar = (today - min(days)).days + 1
    assert 0 <= state.current <= state.best <= len(days)  # заморозка серию не удлиняет
    assert state.best <= calendar
    assert 0 <= state.freezes <= 2


@given(DAY_OFFSETS, st.integers(min_value=0, max_value=6))
def test_extra_freeze_days_never_shorten_the_streak(offsets: set[int], weekend_day: int) -> None:
    days = [at(n) for n in offsets]
    today = max(days)
    base = streak_state(days, today, NEW).current
    with_weekend = streak_state(days, today, StreakRules(weekend_days=frozenset({weekend_day})))
    assert with_weekend.current >= base  # выходной день ничего не отнимает


def test_bought_freeze_covers_the_missed_day_of_purchase() -> None:
    """Купленная в пропущенный день заморозка закрывает его же и не даёт обрыва."""
    rules = StreakRules(bought=frozenset({at(1)}))  # вторник пропущен и в нём покупка
    state = streak_state(d(0, 2), at(2), rules)
    assert (state.current, state.freezes, state.breaks) == (2, 1, ())  # пн и ср, кап 2


def test_bought_freeze_on_active_day_keeps_stock_for_later() -> None:
    """Покупка в активный день после двух пропусков снова даёт запас к пропущенному дню."""
    rules = StreakRules(bought=frozenset({at(4)}))  # пн, ср, пт; вт и чт закрыты запасом
    state = streak_state(d(0, 2, 4), at(5), rules)
    assert (state.current, state.freezes, state.breaks) == (3, 1, ())


def test_bought_freeze_respects_cap() -> None:
    """Купленное поверх полного запаса не даёт запаса больше двух."""
    rules = StreakRules(bought=frozenset({at(0), at(2)}))  # обе покупки — активные дни
    state = streak_state(d(0, 2), at(2), rules)
    assert state.freezes == 2


def test_bought_freeze_after_break_day_belongs_to_new_streak() -> None:
    """Покупка позже дня обрыва старую серию не спасает, но достаётся новой."""
    rules = StreakRules(bought=frozenset({at(4)}))  # запас кончился в чт, покупка в пт
    state = streak_state(d(0, 6), at(6), rules)
    assert [(b.broken_on, b.streak_before) for b in state.breaks] == [(at(3), 1)]
    assert state.current == 1
    assert state.freezes == 1


def test_bought_freeze_today_is_in_stock_even_before_activity() -> None:
    """Покупка «сегодня» уже в запасе, даже если день ещё не закрыт записью."""
    rules = StreakRules(bought=frozenset({at(3)}))
    state = streak_state(d(0, 2), at(3), rules)  # вторник закрыт запасом, сегодня — покупка
    assert state.current == 2
    assert state.freezes == 2


@given(DAY_OFFSETS, st.integers(min_value=0, max_value=30))
def test_bought_freezes_never_shorten_the_streak(offsets: set[int], idle: int) -> None:
    """С любыми покупками серия не короче, чем без них (ADR 0006: ничего не отнимается)."""
    days = [at(n) for n in offsets]
    today = max(days) + timedelta(days=idle)
    base = streak_state(days, today, NEW)
    bought_state = streak_state(days, today, StreakRules(bought=frozenset(days[:3])))
    assert bought_state.current >= base.current
    assert bought_state.freezes >= base.freezes
