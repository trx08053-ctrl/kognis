"""Баланс опыта мотивации 2.0: правила XP и дневной потолок (kognis-0a8, AC1)."""

import itertools
from datetime import date

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from kognis.db import transaction
from kognis.gameplay import GameplayService
from kognis.gameplay._domain import (
    CAPPED_KINDS,
    DAILY_XP_CAP,
    MARKS,
    capped_xp,
    clean_marks,
    reflection_bonus,
)
from kognis.gameplay._infra import ProgressRepository

DAY = date(2026, 9, 1)
OWNERS = itertools.count(1000)


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_each_action_gives_its_xp(engine: Engine) -> None:
    with transaction(engine) as session:
        service = GameplayService(session)
        assert service.award_entry(1, 1, DAY, DAY).xp == 10
        assert service.award_day_review(1, DAY, DAY).xp == 25  # итог дня +15
        assert service.award_analysis_answer(1, 7, DAY).xp == 35  # ответ разбора +10
        assert service.award_analysis_answer(1, 7, DAY).xp == 35  # повтор ничего не даёт
        assert service.award_entry(1, 2, DAY, DAY, ["step", "good"]).xp == 55  # 10 + 2×5


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_reflection_bonus_is_five_to_fifteen_and_ignores_text(engine: Engine) -> None:
    assert [reflection_bonus(MARKS[:n]) for n in range(5)] == [0, 5, 10, 15, 15]
    assert reflection_bonus(["step", "step", "unknown"]) == 5  # повторы и неизвестное не считаются
    assert clean_marks(["insight", "step", "x"]) == ("step", "insight")
    with transaction(engine) as session:
        service = GameplayService(session)
        long_text_no_marks = service.award_entry(1, 1, DAY, DAY, [])  # объём не награждается
        assert long_text_no_marks.xp == 10
        assert service.award_day_review(1, DAY, DAY, ["insight"]).xp == 10 + 15 + 5


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_bonus_once_per_source_and_marks_can_be_added_to_a_review_later(engine: Engine) -> None:
    with transaction(engine) as session:
        service = GameplayService(session)
        assert service.award_day_review(1, DAY, DAY).xp == 15
        assert service.award_day_review(1, DAY, DAY, ["good"]).xp == 20  # отметка добавлена позже
        assert service.award_day_review(1, DAY, DAY, ["good", "step"]).xp == 20  # второй раз нет


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_daily_cap_is_sixty_and_extra_sources_are_recorded_with_zero(engine: Engine) -> None:
    assert capped_xp(15, 50) == 10
    assert capped_xp(15, 60) == 0
    assert capped_xp(15, 0) == 15
    with transaction(engine) as session:
        service = GameplayService(session)
        for entry_id in range(1, 4):
            service.award_entry(1, entry_id, DAY, DAY, ["step", "good", "reframe"])  # по 25
        progress = service.award_day_review(1, DAY, DAY, ["insight"])
    assert progress.xp == DAILY_XP_CAP
    # следующий день — свой потолок
    with transaction(engine) as session:
        assert (
            GameplayService(session).award_entry(1, 9, date(2026, 9, 2), date(2026, 9, 2)).xp == 70
        )


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_reflection_event_is_unique_per_source_in_the_database(engine: Engine) -> None:
    with transaction(engine) as session:
        repo = ProgressRepository(session)
        repo.add_reflection_once(1, "entry:1", DAY, 15, "step,good")
        repo.add_reflection_once(1, "entry:1", DAY, 15, "step,good")  # параллельный повтор
        assert repo.xp_on_day(1, CAPPED_KINDS, DAY) == 15
        assert repo.reflection_marks(1) == [frozenset({"step", "good"})]


def _day_sum(session: Session, owner: int) -> int:
    return ProgressRepository(session).xp_on_day(owner, CAPPED_KINDS, DAY)


ACTIONS = st.one_of(
    st.tuples(st.just("entry"), st.lists(st.sampled_from(MARKS), max_size=4)),
    st.tuples(st.just("review"), st.lists(st.sampled_from(MARKS), max_size=4)),
    st.tuples(st.just("answer"), st.just([])),
)


@pytest.mark.acceptance("kognis-0a8", "AC1")
@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(actions=st.lists(ACTIONS, max_size=25))
def test_sum_per_day_never_exceeds_cap(
    engine: Engine, actions: list[tuple[str, list[str]]]
) -> None:
    owner = next(OWNERS)
    with transaction(engine) as session:
        service = GameplayService(session)
        for n, (kind, marks) in enumerate(actions):
            if kind == "entry":
                service.award_entry(owner, n, DAY, DAY, marks)
            elif kind == "review":
                service.award_day_review(owner, DAY, DAY, marks)
            else:
                service.award_analysis_answer(owner, n, DAY)
            assert _day_sum(session, owner) <= DAILY_XP_CAP
        assert service.progress(owner, DAY).xp <= DAILY_XP_CAP
