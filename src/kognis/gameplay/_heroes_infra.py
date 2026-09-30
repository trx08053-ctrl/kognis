"""Хранение героев: таблицы `companions` и `companion_postcards` принадлежат модулю gameplay."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import KIND_DAY_REVIEW
from ._heroes import MAX_NAME_LENGTH, Postcard
from ._infra import xp_events_table

companions_table = Table(
    "companions",
    metadata,
    Column("owner_id", Integer, primary_key=True, autoincrement=False),
    Column("appearance", String(16), nullable=False),
    Column("name", String(MAX_NAME_LENGTH), nullable=False),
    Column("address", String(2), nullable=False),
    Column("stage_seen", Integer, nullable=False),
    Column("created_on", Date, nullable=False),
)

postcards_table = Table(
    "companion_postcards",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False, index=True),
    Column("day", Date, nullable=False),  # когда принесена
    Column("for_day", Date, nullable=False),  # за какой итог дня
    Column("code", String(32), nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "day", name="uq_companion_postcards_owner_day"),
)


@dataclass(frozen=True)
class CompanionRow:
    appearance: str
    name: str
    address: str
    stage_seen: int


class HeroRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def companion(self, owner_id: int) -> CompanionRow | None:
        t = companions_table
        row = self._session.execute(select(t).where(t.c.owner_id == owner_id)).first()
        if row is None:
            return None
        return CompanionRow(row.appearance, row.name, row.address, row.stage_seen)

    def save_companion(self, owner_id: int, row: CompanionRow, today: date) -> None:
        """Создать спутника или обновить выбор.

        У нового стадия сразу «замечена» (`row.stage_seen`): знакомство — не новая стадия.
        """
        t = companions_table
        exists = self._session.execute(select(t.c.owner_id).where(t.c.owner_id == owner_id)).first()
        if exists:
            self._session.execute(
                update(t)
                .where(t.c.owner_id == owner_id)
                .values(appearance=row.appearance, name=row.name, address=row.address)
            )
            return
        self._session.execute(
            insert(t).values(
                owner_id=owner_id,
                appearance=row.appearance,
                name=row.name,
                address=row.address,
                stage_seen=row.stage_seen,
                created_on=today,
            )
        )

    def mark_stage_seen(self, owner_id: int, stage: int) -> None:
        t = companions_table
        self._session.execute(
            update(t)
            .where(t.c.owner_id == owner_id, t.c.stage_seen < stage)
            .values(stage_seen=stage)
        )

    def postcard_on(self, owner_id: int, day: date) -> Postcard | None:
        t = postcards_table
        row = self._session.execute(
            select(t.c.code, t.c.for_day).where(t.c.owner_id == owner_id, t.c.day == day)
        ).first()
        return Postcard(row.code, row.for_day) if row else None

    def latest_postcard_for_day(self, owner_id: int) -> date | None:
        t = postcards_table
        return self._session.execute(
            select(func.max(t.c.for_day)).where(t.c.owner_id == owner_id)
        ).scalar_one()

    def latest_review_before(self, owner_id: int, day: date) -> date | None:
        """Самый поздний итог дня раньше `day`."""
        t = xp_events_table
        return self._session.execute(
            select(func.max(t.c.day)).where(
                t.c.owner_id == owner_id, t.c.kind == KIND_DAY_REVIEW, t.c.day < day
            )
        ).scalar_one()

    def has_review_on(self, owner_id: int, day: date) -> bool:
        t = xp_events_table
        stmt = select(t.c.id).where(
            t.c.owner_id == owner_id, t.c.kind == KIND_DAY_REVIEW, t.c.day == day
        )
        return self._session.execute(stmt).first() is not None

    def add_postcard_once(self, owner_id: int, day: date, for_day: date, code: str) -> None:
        """Одна открытка в день; параллельный запрос, успевший раньше, тихо выигрывает."""
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(postcards_table).values(
                        owner_id=owner_id,
                        day=day,
                        for_day=for_day,
                        code=code,
                        created_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
        except IntegrityError:
            return
