"""Хранение записей (таблица `entries` принадлежит модулю diary)."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Integer, String, Table, Text, insert, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import Entry

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
