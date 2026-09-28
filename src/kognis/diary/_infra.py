"""Хранение записей (таблица `entries` принадлежит модулю diary)."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import DayReview, Entry

entries_table = Table(
    "entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # владелец — id пользователя из users (без внешнего ключа: таблицей users владеет другой модуль)
    Column("owner_id", Integer, nullable=False, index=True),
    Column("entry_date", Date, nullable=False),
    Column("text", Text, nullable=False),
    Column("tags", JSON, nullable=False),
    Column("emotions", JSON, nullable=False),
    Column("protection", String(16), nullable=False, server_default="plain"),
    Column("created_at", DateTime, nullable=False),
)

day_reviews_table = Table(
    "day_reviews",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False),
    Column("review_date", Date, nullable=False),
    Column("wellbeing", Integer, nullable=False),
    Column("mood", Integer, nullable=False),
    Column("reflection", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "review_date", name="uq_day_reviews_owner_date"),
)


def _to_entry(row: Row[tuple[object, ...]]) -> Entry:
    return Entry(
        id=row.id,
        owner_id=row.owner_id,
        entry_date=row.entry_date,
        text=row.text,
        tags=tuple(row.tags),
        emotions=tuple(row.emotions),
        protection=row.protection,
    )


class EntryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        owner_id: int,
        entry_date: date,
        text: str,
        tags: tuple[str, ...],
        emotions: tuple[str, ...],
    ) -> Entry:
        stmt = (
            insert(entries_table)
            .values(
                owner_id=owner_id,
                entry_date=entry_date,
                text=text,
                tags=list(tags),
                emotions=list(emotions),
                protection="plain",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            .returning(entries_table.c.id)
        )
        entry_id = self._session.execute(stmt).scalar_one()
        return Entry(int(entry_id), owner_id, entry_date, text, tags, emotions)

    def get(self, owner_id: int, entry_id: int) -> Entry | None:
        stmt = select(entries_table).where(
            entries_table.c.id == entry_id, entries_table.c.owner_id == owner_id
        )
        row = self._session.execute(stmt).first()
        return _to_entry(row) if row else None

    def list_for(self, owner_id: int) -> list[Entry]:
        stmt = (
            select(entries_table)
            .where(entries_table.c.owner_id == owner_id)
            .order_by(entries_table.c.entry_date.desc(), entries_table.c.id.desc())
        )
        return [_to_entry(r) for r in self._session.execute(stmt).all()]


def _to_review(row: Row[tuple[object, ...]]) -> DayReview:
    return DayReview(
        id=row.id,
        owner_id=row.owner_id,
        review_date=row.review_date,
        wellbeing=row.wellbeing,
        mood=row.mood,
        reflection=row.reflection,
    )


class DayReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self, owner_id: int, review_date: date, wellbeing: int, mood: int, reflection: str
    ) -> DayReview:
        now = datetime.now(UTC).replace(tzinfo=None)
        table = day_reviews_table
        where = (table.c.owner_id == owner_id, table.c.review_date == review_date)
        existing = self._session.execute(select(table.c.id).where(*where)).scalar_one_or_none()
        if existing is None:
            review_id = self._session.execute(
                insert(table)
                .values(
                    owner_id=owner_id,
                    review_date=review_date,
                    wellbeing=wellbeing,
                    mood=mood,
                    reflection=reflection,
                    created_at=now,
                    updated_at=now,
                )
                .returning(table.c.id)
            ).scalar_one()
        else:
            review_id = existing
            self._session.execute(
                update(table)
                .where(*where)
                .values(wellbeing=wellbeing, mood=mood, reflection=reflection, updated_at=now)
            )
        return DayReview(int(review_id), owner_id, review_date, wellbeing, mood, reflection)

    def list_for(self, owner_id: int) -> list[DayReview]:
        stmt = (
            select(day_reviews_table)
            .where(day_reviews_table.c.owner_id == owner_id)
            .order_by(day_reviews_table.c.review_date.desc())
        )
        return [_to_review(r) for r in self._session.execute(stmt).all()]
