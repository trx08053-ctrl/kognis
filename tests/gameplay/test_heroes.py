"""Цифровые герои, правила: приёмочный kognis-zjg AC1 — стадия спутника по дням с дневником."""

from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.errors import CodedValueError
from kognis.gameplay._heroes import (
    STAGE_DAYS,
    LineContext,
    choose_line,
    companion_stage,
    days_to_next_stage,
    validate_companion,
)
from kognis.gameplay._heroes_infra import HeroRepository

TODAY = date(2026, 9, 10)


@pytest.mark.acceptance("kognis-zjg", "AC1")
@pytest.mark.parametrize(
    ("days", "stage"),
    [(0, 1), (6, 1), (7, 2), (20, 2), (21, 3), (44, 3), (45, 4), (89, 4), (90, 5), (1000, 5)],
)
def test_stage_follows_days_with_diary(days: int, stage: int) -> None:
    assert companion_stage(days) == stage


@pytest.mark.acceptance("kognis-zjg", "AC1")
@given(st.integers(min_value=0, max_value=400), st.integers(min_value=0, max_value=400))
def test_stage_never_drops_when_days_grow_or_pause(days: int, more: int) -> None:
    assert companion_stage(days + more) >= companion_stage(days)  # пауза = +0 дней: стадия та же


@pytest.mark.acceptance("kognis-zjg", "AC1")
def test_days_to_next_stage() -> None:
    assert days_to_next_stage(0) == STAGE_DAYS[1]
    assert days_to_next_stage(89) == 1
    assert days_to_next_stage(90) is None


BASE = LineContext(
    stage=2,
    stage_seen=2,
    last_active=TODAY - timedelta(days=1),
    reviewed_today=False,
    active_today=False,
    streak=5,
    today=TODAY,
)


def _line(**over: Any) -> str | None:
    found = choose_line(replace(BASE, **over))
    return found.situation if found else None


def test_one_line_by_priority_without_mentioning_a_gap() -> None:
    assert _line() == "streak_risk"
    assert _line(stage=3) == "new_stage"
    assert _line(last_active=TODAY - timedelta(days=9)) == "return"
    assert _line(reviewed_today=True, active_today=True) == "after_summary"
    assert _line(active_today=True, last_active=TODAY) is None
    assert _line(streak=1) is None


def test_companion_choice_is_validated() -> None:
    assert validate_companion("fox", "  Луна ", "ty") == "Луна"
    for bad in (
        ("dragon", "Луна", "ty"),
        ("fox", "", "ty"),
        ("fox", "x" * 25, "ty"),
        ("fox", "Л", "z"),
    ):
        with pytest.raises(CodedValueError):
            validate_companion(*bad)


def test_postcard_is_written_once_per_day(engine: Engine) -> None:
    with transaction(engine) as session:
        repo = HeroRepository(session)
        repo.add_postcard_once(1, TODAY, TODAY - timedelta(days=1), "cbt_1")
        repo.add_postcard_once(1, TODAY, TODAY - timedelta(days=1), "act_2")  # гонка: второй молчит
        card = repo.postcard_on(1, TODAY)
    assert card is not None
    assert card.code == "cbt_1"
