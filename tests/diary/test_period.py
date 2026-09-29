"""Выборка записей и итогов дня за период: kognis-pj6 AC2, AC3 (через публичный API модулей)."""

import json
from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.analysis import AnalysisService
from kognis.db import transaction
from kognis.diary import DiaryService

START, END = date(2026, 9, 3), date(2026, 9, 5)


def seed(engine: Engine) -> None:
    with transaction(engine) as session:
        diary = DiaryService(session)
        for day in (2, 3, 4, 5, 6):
            diary.create_entry(1, f"запись {day}", [], [], date(2026, 9, day))
            diary.save_day_review(1, date(2026, 9, day), 3, 3, f"итог {day}")
        diary.create_entry(2, "чужая внутри периода", [], [], date(2026, 9, 4))
        diary.save_day_review(2, date(2026, 9, 4), 1, 1, "чужой итог")


@pytest.mark.acceptance("kognis-pj6", "AC2")
def test_period_bounds_inclusive_and_owner_only(engine: Engine) -> None:
    seed(engine)
    with transaction(engine) as session:
        diary = DiaryService(session)
        entries = diary.list_entries_between(1, START, END)
        reviews = diary.list_day_reviews_between(1, START, END)
    assert sorted(e.entry_date.day for e in entries) == [3, 4, 5]
    assert sorted(r.review_date.day for r in reviews) == [3, 4, 5]
    assert all(e.owner_id == 1 for e in entries)
    assert all(r.owner_id == 1 for r in reviews)


@pytest.mark.acceptance("kognis-pj6", "AC2")
def test_period_filter_is_in_sql(engine: Engine) -> None:
    seed(engine)
    statements: list[str] = []

    def capture(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with transaction(engine) as session:
            DiaryService(session).list_entries_between(1, START, END)
            DiaryService(session).list_day_reviews_between(1, START, END)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    for table, column in (("entries", "entry_date"), ("day_reviews", "review_date")):
        selects = [s for s in statements if f"FROM {table}" in s]
        assert len(selects) == 1
        assert f"{table}.{column} >=" in selects[0]
        assert f"{table}.{column} <=" in selects[0]


class RecordingProvider:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        self.sent.append(messages[0].content)
        return json.dumps({"summary": "ок", "patterns": [], "questions": [], "quest_ideas": []})


@pytest.mark.acceptance("kognis-pj6", "AC3")
def test_analysis_sends_only_period_data(engine: Engine) -> None:
    seed(engine)
    provider = RecordingProvider()
    with transaction(engine) as session:
        outcome = AnalysisService(session, provider).analyze(1, "cbt", START, END, consent=True)
    assert outcome.analysis.status == "done"
    sent = provider.sent[0]
    for day in (3, 4, 5):
        assert f"запись {day}" in sent
        assert f"итог {day}" in sent
    for day in (2, 6):
        assert f"запись {day}" not in sent
        assert f"итог {day}" not in sent
    assert "чуж" not in sent
