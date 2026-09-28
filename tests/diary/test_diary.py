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
        assert [e.text for e in service.list_entries(1)] == ["моя"]
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
