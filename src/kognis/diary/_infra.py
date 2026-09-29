"""Хранение записей (таблица `entries` принадлежит модулю diary)."""

from dataclasses import replace
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    cast,
    false,
    func,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from kognis.db import metadata

from ._crypto import Sealed
from ._domain import DayReview, Entry, EntryFilter, Page, decode_cursor, encode_cursor

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
    # «приватная» (D4): text пуст, конверт (версия, KDF, соль, iv, шифртекст) собран в браузере
    Column("private_envelope", JSON, nullable=True),
    Column("created_at", DateTime, nullable=False),
    # страница «последние записи» и отбор по периоду идут по этому индексу (kognis-3mh)
    Index("ix_entries_owner_date_id", "owner_id", "entry_date", "id"),
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
        envelope=row.private_envelope,
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
        if entry.envelope is not None:
            protection = "private"
        stored = "" if sealed else entry.text
        stmt = (
            insert(entries_table)
            .values(
                private_envelope=entry.envelope,
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

    def has_label(self, column: Column[object], label: str) -> ColumnElement[bool]:
        """Условие «в JSON-списке `column` есть `label`» на диалекте текущей БД."""
        if self._session.get_bind().dialect.name == "postgresql":
            return cast(column, JSONB).contains([label])
        item = func.json_each(column).table_valued("value")
        return select(item.c.value).where(item.c.value == label).exists()

    def page(
        self, owner_id: int, limit: int, cursor: str | None, where: EntryFilter
    ) -> Page[Entry]:
        """Страница записей владельца, новые первыми; курсор — (дата, id) последней выданной."""
        table = entries_table
        conditions = [table.c.owner_id == owner_id]
        if where.tag is not None:
            conditions.append(self.has_label(table.c.tags, where.tag))
        if where.emotion is not None:
            conditions.append(self.has_label(table.c.emotions, where.emotion))
        if where.start is not None:
            conditions.append(table.c.entry_date >= where.start)
        if where.end is not None:
            conditions.append(table.c.entry_date <= where.end)
        if cursor is not None:
            day, last_id = decode_cursor(cursor, with_id=True)
            conditions.append(
                or_(
                    table.c.entry_date < day,
                    and_(table.c.entry_date == day, table.c.id < last_id),
                )
            )
        stmt = (
            select(table)
            .where(*conditions)
            .order_by(table.c.entry_date.desc(), table.c.id.desc())
            .limit(limit + 1)
        )
        rows = self._session.execute(stmt).all()
        items = [_to_entry(r) for r in rows[:limit]]
        more = len(rows) > limit
        return Page(items, encode_cursor(items[-1].entry_date, items[-1].id) if more else None)

    def labels(self, owner_id: int) -> tuple[list[str], list[str]]:
        """Все теги и эмоции владельца (варианты фильтров): читаются лишь два узких столбца."""
        rows = self._session.execute(
            select(entries_table.c.tags, entries_table.c.emotions).where(
                entries_table.c.owner_id == owner_id
            )
        ).all()
        return (
            sorted({t for r in rows for t in r.tags}),
            sorted({e for r in rows for e in r.emotions}),
        )

    def list_between(self, owner_id: int, start: date, end: date) -> list[Entry]:
        """Записи владельца за период (границы включительно); фильтр — в запросе к БД."""
        stmt = (
            select(entries_table)
            .where(
                entries_table.c.owner_id == owner_id,
                entries_table.c.entry_date >= start,
                entries_table.c.entry_date <= end,
            )
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

    def page(self, owner_id: int, limit: int, cursor: str | None) -> Page[DayReview]:
        """Страница итогов владельца, новые первыми; курсор — дата последнего выданного."""
        table = day_reviews_table
        conditions = [table.c.owner_id == owner_id]
        if cursor is not None:
            conditions.append(table.c.review_date < decode_cursor(cursor, with_id=False)[0])
        stmt = (
            select(table).where(*conditions).order_by(table.c.review_date.desc()).limit(limit + 1)
        )
        rows = self._session.execute(stmt).all()
        items = [_to_review(r) for r in rows[:limit]]
        return Page(items, encode_cursor(items[-1].review_date) if len(rows) > limit else None)

    def list_between(self, owner_id: int, start: date, end: date) -> list[DayReview]:
        """Итоги дня владельца за период (границы включительно); фильтр — в запросе к БД."""
        table = day_reviews_table
        stmt = (
            select(table)
            .where(
                table.c.owner_id == owner_id,
                table.c.review_date >= start,
                table.c.review_date <= end,
            )
            .order_by(table.c.review_date.desc())
        )
        return [_to_review(r) for r in self._session.execute(stmt).all()]
