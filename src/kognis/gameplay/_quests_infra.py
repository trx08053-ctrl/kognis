"""Хранение квестов и ответов квизов (таблицы принадлежат модулю gameplay)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Integer,
    Row,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._quests import SOURCE_ANALYSIS, Quest, QuestStep, QuizAnswers

quests_table = Table(
    "quests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False, index=True),
    Column("source", String(16), nullable=False),
    # источник: код шаблона библиотеки или «id анализа:номер идеи» — повторно принять нельзя
    Column("source_ref", String(64), nullable=False),
    Column("template_code", String(32), nullable=True),
    Column("kind", String(16), nullable=False),
    Column("title", String(200), nullable=False),
    Column("description", Text, nullable=False),
    Column("created_on", Date, nullable=False),
    Column("completed_on", Date, nullable=True),
    Column("created_at", DateTime, nullable=False),
)

quest_steps_table = Table(
    "quest_steps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("quest_id", Integer, nullable=False, index=True),
    Column("idx", Integer, nullable=False),
    Column("title", Text, nullable=False),
    Column("done_on", Date, nullable=True),
    UniqueConstraint("quest_id", "idx", name="uq_quest_steps_quest_idx"),
)

quiz_answers_table = Table(
    "quiz_answers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False, index=True),
    Column("quiz_code", String(32), nullable=False),
    Column("day", Date, nullable=False),
    Column("answers", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "quiz_code", "day", name="uq_quiz_answers_owner_quiz_day"),
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class NewQuest:
    source: str
    source_ref: str
    template_code: str | None
    kind: str
    title: str
    description: str
    steps: tuple[str, ...]


class QuestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_quest(self, owner_id: int, new: NewQuest, today: date) -> Quest:
        quest_id = self._session.execute(
            insert(quests_table)
            .values(
                owner_id=owner_id,
                source=new.source,
                source_ref=new.source_ref,
                template_code=new.template_code,
                kind=new.kind,
                title=new.title,
                description=new.description,
                created_on=today,
                created_at=_now(),
            )
            .returning(quests_table.c.id)
        ).scalar_one()
        for idx, step_title in enumerate(new.steps):
            self._session.execute(
                insert(quest_steps_table).values(quest_id=quest_id, idx=idx, title=step_title)
            )
        return self.fetch(quest_id)

    def has_open(self, owner_id: int, source: str, source_ref: str) -> bool:
        """Есть принятый квест из этого источника: не завершённый (анализ — любой)."""
        t = quests_table
        stmt = select(t.c.completed_on).where(
            t.c.owner_id == owner_id, t.c.source == source, t.c.source_ref == source_ref
        )
        rows = self._session.execute(stmt).all()
        return any(r.completed_on is None or source == SOURCE_ANALYSIS for r in rows)

    def get(self, owner_id: int, quest_id: int) -> Quest | None:
        t = quests_table
        row = self._session.execute(
            select(t).where(t.c.owner_id == owner_id, t.c.id == quest_id)
        ).first()
        return self._build(row) if row else None

    def fetch(self, quest_id: int) -> Quest:
        """Квест по id без проверки владельца — только для уже проверенных id."""
        t = quests_table
        return self._build(self._session.execute(select(t).where(t.c.id == quest_id)).one())

    def list_for(self, owner_id: int) -> list[Quest]:
        t = quests_table
        rows = self._session.execute(
            select(t).where(t.c.owner_id == owner_id).order_by(t.c.id.desc())
        ).all()
        return [self._build(r) for r in rows]

    def mark_step(self, quest_id: int, idx: int, day: date) -> None:
        s = quest_steps_table
        self._session.execute(
            update(s).where(s.c.quest_id == quest_id, s.c.idx == idx).values(done_on=day)
        )

    def complete(self, quest_id: int, day: date) -> None:
        t = quests_table
        self._session.execute(update(t).where(t.c.id == quest_id).values(completed_on=day))

    def _build(self, row: Row[Any]) -> Quest:
        s = quest_steps_table
        steps = self._session.execute(
            select(s).where(s.c.quest_id == row.id).order_by(s.c.idx)
        ).all()
        return Quest(
            id=row.id,
            source=row.source,
            template_code=row.template_code,
            kind=row.kind,
            title=row.title,
            description=row.description,
            created_on=row.created_on,
            completed_on=row.completed_on,
            steps=tuple(QuestStep(r.idx, r.title, r.done_on) for r in steps),
        )


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def done_codes(self, owner_id: int, day: date) -> set[str]:
        t = quiz_answers_table
        stmt = select(t.c.quiz_code).where(t.c.owner_id == owner_id, t.c.day == day)
        return {r.quiz_code for r in self._session.execute(stmt).all()}

    def add(self, owner_id: int, quiz_code: str, day: date, answers: tuple[str, ...]) -> None:
        self._session.execute(
            insert(quiz_answers_table).values(
                owner_id=owner_id,
                quiz_code=quiz_code,
                day=day,
                answers=list(answers),
                created_at=_now(),
            )
        )

    def history(self, owner_id: int, quiz_code: str) -> list[QuizAnswers]:
        t = quiz_answers_table
        stmt = (
            select(t.c.quiz_code, t.c.day, t.c.answers)
            .where(t.c.owner_id == owner_id, t.c.quiz_code == quiz_code)
            .order_by(t.c.day.desc())
        )
        return [
            QuizAnswers(r.quiz_code, r.day, tuple(r.answers))
            for r in self._session.execute(stmt).all()
        ]
