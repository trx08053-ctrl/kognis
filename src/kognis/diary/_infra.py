"""Хранение записей (таблица `entries` принадлежит модулю diary)."""

from dataclasses import replace
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._crypto import Sealed
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
    Column("crisis", Boolean, nullable=False, server_default=false()),
    # «под замком» (D4): text пуст, содержимое — шифртекст; пароль замка — argon2id
    Column("lock_cipher", LargeBinary, nullable=True),
    Column("lock_nonce", LargeBinary, nullable=True),
    Column("lock_hash", String(255), nullable=True),
    Column("lock_version", Integer, nullable=True),
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
        crisis=row.crisis,
    )


def _seal_values(sealed: Sealed | None) -> dict[str, object]:
    return {
        "lock_cipher": sealed.cipher if sealed else None,
        "lock_nonce": sealed.nonce if sealed else None,
        "lock_hash": sealed.lock_hash if sealed else None,
        "lock_version": sealed.version if sealed else None,
    }


class EntryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: Entry, sealed: Sealed | None = None) -> Entry:
        """Сохранить новую запись (`entry.id` игнорируется); с `sealed` текст в БД не пишется."""
        protection = "locked" if sealed else "plain"
        stored = "" if sealed else entry.text
        stmt = (
            insert(entries_table)
            .values(
                owner_id=entry.owner_id,
                entry_date=entry.entry_date,
                text=stored,
                tags=list(entry.tags),
                emotions=list(entry.emotions),
                protection=protection,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                **_seal_values(sealed),
            )
            .returning(entries_table.c.id)
        )
        entry_id = self._session.execute(stmt).scalar_one()
        return replace(entry, id=int(entry_id), text=stored, protection=protection)

    def sealed_for(self, owner_id: int, entry_id: int) -> Sealed | None:
        """Шифрованное содержимое записи владельца (только у `locked`)."""
        table = entries_table
        row = self._session.execute(
            select(
                table.c.lock_cipher, table.c.lock_nonce, table.c.lock_hash, table.c.lock_version
            ).where(table.c.id == entry_id, table.c.owner_id == owner_id)
        ).first()
        if row is None or row.lock_cipher is None:
            return None
        return Sealed(
            bytes(row.lock_cipher), bytes(row.lock_nonce), row.lock_hash, row.lock_version
        )

    def set_protection(
        self, owner_id: int, entry_id: int, text: str, sealed: Sealed | None
    ) -> None:
        """Сменить режим: `sealed` — закрыть замком (text очищается), `None` — вернуть `text`.

        Условие по текущему режиму: проигравший гонку двух запросов ничего не перезапишет.
        """
        was = "plain" if sealed else "locked"
        self._session.execute(
            update(entries_table)
            .where(
                entries_table.c.id == entry_id,
                entries_table.c.owner_id == owner_id,
                entries_table.c.protection == was,
            )
            .values(
                text="" if sealed else text,
                protection="locked" if sealed else "plain",
                **_seal_values(sealed),
            )
        )

    def set_crisis(self, owner_id: int, entry_id: int) -> Entry | None:
        self._session.execute(
            update(entries_table)
            .where(entries_table.c.id == entry_id, entries_table.c.owner_id == owner_id)
            .values(crisis=True)
        )
        return self.get(owner_id, entry_id)

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
