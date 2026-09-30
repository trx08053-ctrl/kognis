"""Граничные случаи игрового ядра, найденные мутационным тестированием (kognis-8jq)."""

from datetime import date, timedelta

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import GameplayService, _infra
from kognis.gameplay._domain import level_for, level_start, streak_length

MON = date(2026, 9, 7)  # понедельник недели 37; неделя 38 начинается 14 сентября


def _days(*offsets: int) -> list[date]:
    return [MON + timedelta(days=n) for n in offsets]


@pytest.mark.acceptance("kognis-8jq", "AC1")
def test_award_is_once_per_owner_and_entry_but_independent_across_them(engine: Engine) -> None:
    today = date(2026, 9, 1)
    with transaction(engine) as session:
        service = GameplayService(session)
        service.award_entry(1, 100, today, today)
        again = service.award_entry(1, 100, today, today)  # та же запись — второй раз нельзя
        other_entry = service.award_entry(1, 101, today, today)  # другая запись — своё начисление
        other_owner = service.award_entry(2, 100, today, today)  # тот же id у другого пользователя
    assert again.xp == 10
    assert other_entry.xp == 20
    assert other_owner.xp == 10
    assert [a.code for a in other_owner.achievements] == ["first_entry"]


def test_repeated_award_does_not_retry_granted_achievements(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    today = date(2026, 9, 1)
    calls: list[str] = []
    real = _infra.ProgressRepository.add_achievement

    def spy(repo: _infra.ProgressRepository, owner_id: int, code: str, earned_on: date) -> None:
        calls.append(code)
        real(repo, owner_id, code, earned_on)

    monkeypatch.setattr(_infra.ProgressRepository, "add_achievement", spy)
    with transaction(engine) as session:
        service = GameplayService(session)
        service.award_entry(1, 100, today, today)
        service.award_entry(1, 100, today, today)
    assert calls == ["first_entry"]


@pytest.mark.acceptance("kognis-8jq", "AC2")
def test_level_thresholds_and_freeze_week_boundaries() -> None:
    # опыт ровно на пороге даёт этот уровень (в том числе первый «бесконечный»)
    assert level_for(1249) == 9
    assert level_for(1250) == 10
    assert level_for(1549) == 10
    assert level_for(1550) == 11
    assert level_start(10) == 1250
    assert level_start(11) == 1550
    # заморозка недели 37 израсходована (пропущен вт 8 сентября)
    used = _days(0, 2, 3, 4, 5)  # пн, ср, чт, пт, сб
    assert streak_length(used, MON + timedelta(days=5)) == 5
    # пропущено вс 13 (неделя 37, заморозка уже потрачена) — серия сбрасывается
    assert streak_length(used, MON + timedelta(days=7)) == 0
    # последняя активность — вс; пропущен пн 14 (неделя 38) — заморозка свободна
    sunday = _days(0, 2, 3, 4, 5, 6)
    assert streak_length(sunday, MON + timedelta(days=8)) == 6
    # без израсходованной заморозки пропуск вс 13 гасится
    assert streak_length(_days(2, 3, 4, 5), MON + timedelta(days=7)) == 4
    # через три дня после последней активности серии нет
    assert streak_length(_days(2, 3, 4, 5), MON + timedelta(days=8)) == 0


@pytest.mark.acceptance("kognis-0a8", "AC4")
def test_answer_and_day_review_are_once_per_owner_and_source(engine: Engine) -> None:
    today = date(2026, 9, 1)
    with transaction(engine) as session:
        service = GameplayService(session)
        service.award_analysis_answer(1, 7, today)
        repeat = service.award_analysis_answer(1, 7, today)
        other_analysis = service.award_analysis_answer(1, 8, today)
        other_owner = service.award_analysis_answer(2, 7, today)
        service.award_day_review(1, today, today)
        review_again = service.award_day_review(1, today, today)
        review_other_owner = service.award_day_review(2, today, today)
    assert repeat.xp == 10
    assert other_analysis.xp == 20
    assert other_owner.xp == 10
    assert review_again.xp == 35  # 10 + 10 + 15: повтор итога дня XP не даёт
    assert review_other_owner.xp == 25


@pytest.mark.acceptance("kognis-0a8", "AC4")
def test_reflection_bonus_is_once_per_source_and_independent_across_owners(engine: Engine) -> None:
    today = date(2026, 9, 1)
    with transaction(engine) as session:
        service = GameplayService(session)
        first = service.award_entry(1, 100, today, today, ["good"])
        again = service.award_entry(1, 100, today, today, ["good"])
        other_owner = service.award_entry(2, 100, today, today, ["good"])
    assert first.xp > 10
    assert again.xp == first.xp
    assert other_owner.xp == first.xp
