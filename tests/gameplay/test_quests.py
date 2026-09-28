"""QuestService: устойчивость к параллельным запросам (гонка имитируется «устаревшим» чтением)."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import GameplayService, QuestService, QuizDoneTodayError, _quests_infra

TODAY = date(2026, 9, 1)
ANSWERS = ["а", "б", "в"]


def test_concurrent_quiz_submit_gives_conflict_and_single_xp(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with transaction(engine) as session:
        QuestService(session).submit_quiz(1, "evening", ANSWERS, TODAY, reward=True)

    def stale(_repo: object, _owner_id: int, _day: date) -> set[str]:
        return set()

    monkeypatch.setattr(_quests_infra.QuizRepository, "done_codes", stale)
    with pytest.raises(QuizDoneTodayError), transaction(engine) as session:
        QuestService(session).submit_quiz(1, "evening", ANSWERS, TODAY, reward=True)
    with transaction(engine) as session:
        assert GameplayService(session).progress(1, TODAY).xp == 10


def test_concurrent_step_mark_gives_no_second_xp(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with transaction(engine) as session:
        quest = QuestService(session).accept_template(1, "catch_thought", TODAY)
        stale = QuestService(session).complete_step(1, quest.id, 0, TODAY)
    assert stale is not None
    assert stale.xp == 15

    fresh = quest  # состояние до отметки: шаг выглядит невыполненным

    def stale_get(_repo: object, _owner_id: int, _quest_id: int) -> object:
        return fresh

    monkeypatch.setattr(_quests_infra.QuestRepository, "get", stale_get)
    with transaction(engine) as session:
        outcome = QuestService(session).complete_step(1, quest.id, 0, TODAY)
    assert outcome is not None
    assert outcome.xp == 0
    with transaction(engine) as session:
        assert GameplayService(session).progress(1, TODAY).xp == 15
