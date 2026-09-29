"""Границы итога дня: оценки и длина рефлексии (найдено мутационным тестированием, kognis-8jq)."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import DiaryService
from kognis.diary._domain import MAX_REFLECTION_LENGTH

DAY = date(2026, 9, 1)


def _save(engine: Engine, wellbeing: int, mood: int, reflection: str = "") -> tuple[int, int]:
    with transaction(engine) as session:
        review = DiaryService(session).save_day_review(1, DAY, wellbeing, mood, reflection)
    return review.wellbeing, review.mood


@pytest.mark.acceptance("kognis-8jq", "AC3")
def test_scale_edges_and_reflection_length_edge(engine: Engine) -> None:
    assert _save(engine, 1, 10) == (1, 10)
    assert _save(engine, 10, 1) == (10, 1)
    assert _save(engine, 5, 5, "я" * MAX_REFLECTION_LENGTH) == (5, 5)
    for wellbeing, mood in [(0, 5), (11, 5)]:
        with pytest.raises(ValueError, match=r"^самочувствие: оценка от 1 до 10$"):
            _save(engine, wellbeing, mood)
    for wellbeing, mood in [(5, 0), (5, 11)]:
        with pytest.raises(ValueError, match=r"^настроение: оценка от 1 до 10$"):
            _save(engine, wellbeing, mood)
    with pytest.raises(ValueError, match=r"^рефлексия слишком длинная$"):
        _save(engine, 5, 5, "я" * (MAX_REFLECTION_LENGTH + 1))
