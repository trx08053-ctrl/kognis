from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import DiaryService
from kognis.diary._domain import normalize_labels


def test_entry_persists_and_is_normalized(engine: Engine) -> None:
    with transaction(engine) as session:
        entry = DiaryService(session).create_entry(
            1, "  Тяжёлый день ", [" Работа ", "работа", "сон"], ["Тревога"], date(2026, 9, 1)
        )
    with transaction(engine) as session:
        assert DiaryService(session).get_entry(1, entry.id) == entry
    assert entry.text == "Тяжёлый день"
    assert entry.tags == ("работа", "сон")
    assert entry.emotions == ("тревога",)


def test_owner_isolation_in_service(engine: Engine) -> None:
    with transaction(engine) as session:
        service = DiaryService(session)
        mine = service.create_entry(1, "моя", [], [])
        service.create_entry(2, "чужая", [], [])
    with transaction(engine) as session:
        service = DiaryService(session)
        assert [e.text for e in service.list_entries(1).items] == ["моя"]
        assert service.get_entry(2, mine.id) is None


def test_blank_text_rejected(engine: Engine) -> None:
    with pytest.raises(ValueError, match="пуст"), transaction(engine) as session:
        DiaryService(session).create_entry(1, "   ", [], [])


def test_too_many_labels_rejected() -> None:
    with pytest.raises(ValueError, match="не больше"):
        normalize_labels([str(i) for i in range(30)], "теги")


@given(st.lists(st.text(alphabet="abcXYZ ", max_size=10), max_size=15))
def test_labels_are_unique_lowercase(raw: list[str]) -> None:
    result = normalize_labels(raw, "теги")
    assert len(set(result)) == len(result)
    assert all(label == label.strip().lower() and label for label in result)


def test_day_review_upsert_is_per_owner_and_date(engine: Engine) -> None:
    with transaction(engine) as session:
        service = DiaryService(session)
        first = service.save_day_review(1, date(2026, 9, 1), 5, 5, "")
        again = service.save_day_review(1, date(2026, 9, 1), 6, 7, " ок ")
        other = service.save_day_review(2, date(2026, 9, 1), 1, 1, "")
    assert again.id == first.id
    assert (again.wellbeing, again.mood, again.reflection) == (6, 7, "ок")
    assert other.id != first.id
    with transaction(engine) as session:
        assert len(DiaryService(session).list_day_reviews(1).items) == 1


@pytest.mark.parametrize(("wellbeing", "mood"), [(0, 5), (5, 0), (11, 5), (5, 11)])
def test_day_review_scale_bounds(engine: Engine, wellbeing: int, mood: int) -> None:
    with pytest.raises(ValueError, match="от 1 до 10"), transaction(engine) as session:
        DiaryService(session).save_day_review(1, date(2026, 9, 1), wellbeing, mood, "")
