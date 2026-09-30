"""Границы начисления: владелец, источник, отметки (kognis-0a8, по итогам мутационного прогона)."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import GameplayService, QuestService
from kognis.gameplay._quests import QUIZZES

DAY = date(2026, 9, 1)


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_answer_bonus_is_per_owner_and_per_analysis(engine: Engine) -> None:
    with transaction(engine) as session:
        service = GameplayService(session)
        assert service.award_analysis_answer(1, 7, DAY).xp == 10
        assert service.award_analysis_answer(1, 8, DAY).xp == 20  # другой разбор — своё начисление
        assert service.award_analysis_answer(2, 7, DAY).xp == 10  # другой владелец — свои права


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_reflection_bonus_is_per_owner_and_per_source(engine: Engine) -> None:
    with transaction(engine) as session:
        service = GameplayService(session)
        assert service.award_entry(1, 1, DAY, DAY, ["step"]).xp == 15
        assert service.award_entry(2, 1, DAY, DAY, ["step"]).xp == 15  # тот же id у другого
        assert service.award_day_review(1, DAY, DAY, ["good"]).xp == 15 + 15 + 5  # другой источник


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_marks_are_stored_whole_and_quizzes_count_once_per_code(engine: Engine) -> None:
    with transaction(engine) as session:
        service = GameplayService(session)
        service.award_entry(1, 1, DAY, DAY, ["step", "good"])
        progress = service.progress(1, DAY)
        depth = next(c for c in progress.categories if c.category == "depth")
        assert depth.value == 1  # «шаг» распознан среди нескольких отметок
        assert progress.hidden[1].earned_on == DAY  # «хорошее» — первая благодарность
        quiz = QUIZZES[0]
        answers = ["ответ"] * len(quiz.questions)
        quests = QuestService(session)
        quests.submit_quiz(1, quiz.code, answers, DAY, reward=True)
        quests.submit_quiz(1, quiz.code, answers, date(2026, 9, 2), reward=True)  # тот же квиз
        explorer = next(c for c in service.progress(1, DAY).categories if c.category == "explorer")
        assert explorer.value == 1


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_weekly_goal_bonus_is_once_per_owner_and_week(engine: Engine) -> None:
    days = [date(2026, 9, 7), date(2026, 9, 8), date(2026, 9, 9)]  # пн–ср, цель 3
    with transaction(engine) as session:
        service = GameplayService(session)
        for owner in (1, 2):
            for n, day in enumerate(days):
                service.award_entry(owner, n, day, day)
            assert service.progress(owner, days[-1]).xp == 30 + 30  # три записи + бонус недели
        service.award_entry(1, 9, days[-1], days[-1])  # ещё запись — бонус не повторяется
        after = service.progress(1, days[-1])
        assert after.xp == 60 + 10
        assert (after.days_total, after.days_30) == (3, 3)
