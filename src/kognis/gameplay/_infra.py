"""Хранение прогресса (таблицы `xp_events` и `achievements` принадлежат модулю gameplay)."""

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
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.db import metadata

STREAK_KINDS = ("entry", "day_review")

xp_events_table = Table(
    "xp_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # владелец — id пользователя из users (без внешнего ключа: таблицей users владеет другой модуль)
    Column("owner_id", Integer, nullable=False),
    Column("kind", String(32), nullable=False),
    # источник события (id записи, дата итога): повторное начисление за него невозможно
    Column("ref", String(64), nullable=False),
    Column("day", Date, nullable=False),
    Column("xp", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "kind", "ref", name="uq_xp_events_owner_kind_ref"),
)

achievements_table = Table(
    "achievements",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False),
    Column("code", String(32), nullable=False),
    Column("earned_on", Date, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "code", name="uq_achievements_owner_code"),
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ProgressRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def has_event(self, owner_id: int, kind: str, ref: str) -> bool:
        t = xp_events_table
        stmt = select(t.c.id).where(t.c.owner_id == owner_id, t.c.kind == kind, t.c.ref == ref)
        return self._session.execute(stmt).first() is not None

    def add_event(self, owner_id: int, kind: str, ref: str, day: date, xp: int) -> None:
        self._session.execute(
            insert(xp_events_table).values(
                owner_id=owner_id, kind=kind, ref=ref, day=day, xp=xp, created_at=_now()
            )
        )

    def count_events(self, owner_id: int, kind: str, day: date | None = None) -> int:
        t = xp_events_table
        stmt = select(func.count()).where(t.c.owner_id == owner_id, t.c.kind == kind)
        if day is not None:
            stmt = stmt.where(t.c.day == day)
        return int(self._session.execute(stmt).scalar_one())

    def total_xp(self, owner_id: int) -> int:
        t = xp_events_table
        stmt = select(func.coalesce(func.sum(t.c.xp), 0)).where(t.c.owner_id == owner_id)
        return int(self._session.execute(stmt).scalar_one())

    def active_days(self, owner_id: int) -> list[date]:
        t = xp_events_table
        # серия — только записи и итоги дня; XP за квесты и квизы дни серии не продлевает
        stmt = (
            select(t.c.day).where(t.c.owner_id == owner_id, t.c.kind.in_(STREAK_KINDS)).distinct()
        )
        return [r.day for r in self._session.execute(stmt).all()]

    def achievements(self, owner_id: int) -> list[tuple[str, date]]:
        t = achievements_table
        stmt = select(t.c.code, t.c.earned_on).where(t.c.owner_id == owner_id).order_by(t.c.id)
        return [(r.code, r.earned_on) for r in self._session.execute(stmt).all()]

    def add_achievement(self, owner_id: int, code: str, earned_on: date) -> None:
        """Выдать достижение; если параллельный запрос успел раньше — тихо ничего не делать.

        Savepoint не даёт конфликту откатить всю транзакцию (вместе с записью дневника).
        """
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(achievements_table).values(
                        owner_id=owner_id, code=code, earned_on=earned_on, created_at=_now()
                    )
                )
        except IntegrityError:
            return
