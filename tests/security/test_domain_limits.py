"""Доменные лимиты ввода (эшелон за схемами API): срабатывают, даже если слой web их пропустил."""

import pytest

from kognis.analysis._domain import MAX_ANSWER_LENGTH, MAX_ANSWERS, normalize_answers
from kognis.diary._domain import (
    MAX_LABEL_LENGTH,
    MAX_REFLECTION_LENGTH,
    MAX_TEXT_LENGTH,
    normalize_labels,
    normalize_reflection,
    normalize_text,
)
from kognis.gameplay import QuizDef
from kognis.gameplay._quests import normalize_quiz_answers
from kognis.users._domain import MAX_PASSWORD_LENGTH, validate_password


def test_diary_text_and_reflection_length_limited() -> None:
    with pytest.raises(ValueError, match=r"diary\.text_long"):
        normalize_text("а" * (MAX_TEXT_LENGTH + 1))
    with pytest.raises(ValueError, match=r"diary\.reflection_long"):
        normalize_reflection("а" * (MAX_REFLECTION_LENGTH + 1))


def test_label_length_limited() -> None:
    with pytest.raises(ValueError, match=r"diary\.tags_item_long"):
        normalize_labels(["а" * (MAX_LABEL_LENGTH + 1)], "tags")


def test_analysis_answers_limited() -> None:
    with pytest.raises(ValueError, match=r"analysis\.answers_long"):
        normalize_answers(["а"] * (MAX_ANSWERS + 1))
    with pytest.raises(ValueError, match=r"analysis\.answers_long"):
        normalize_answers(["а" * (MAX_ANSWER_LENGTH + 1)])


def test_quiz_answer_length_limited() -> None:
    quiz = QuizDef("q", "Q", ("один",))
    with pytest.raises(ValueError, match=r"gameplay\.answer_long"):
        normalize_quiz_answers(quiz, ["а" * (MAX_ANSWER_LENGTH + 1)])


def test_password_length_limited() -> None:
    with pytest.raises(ValueError, match=r"user\.password_long"):
        validate_password("а" * (MAX_PASSWORD_LENGTH + 1))
