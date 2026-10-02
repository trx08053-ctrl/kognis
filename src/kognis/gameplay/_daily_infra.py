"""Выбор задания дня (таблица `daily_picks` принадлежит модулю gameplay).

Один выбор в день — уникальностью (owner, day); повтор в тот же день отклоняется.
"""

from datetime import date

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.db import metadata
from kognis.errors import CodedError

from ._infra import _now

daily_picks_table = Table(
    "daily_picks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # владелец — id пользователя из users (без внешнего ключа: таблицей users владеет другой модуль)
    Column("owner_id", Integer, nullable=False, index=True),
    Column("day", Date, nullable=False),
    # код задания из пула (_daily.DAILY_POOL); текст отдаёт интерфейс по словарю
    Column("code", String(32), nullable=False),
    Column("done_on", Date, nullable=True),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "day", name="uq_daily_picks_owner_day"),
)


class DailyDoneTodayError(CodedError):
    """Задание на этот день уже выбрано: смена выбора не предусмотрена (без штрафа)."""

    def __init__(self) -> None:
        super().__init__("gameplay.daily_picked")


class DailyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def pick_on(self, owner_id: int, day: date) -> tuple[str, date | None] | None:
        """(код выбранного задания, когда выполнено) или None — день ещё без выбора."""
        t = daily_picks_table
        stmt = select(t.c.code, t.c.done_on).where(t.c.owner_id == owner_id, t.c.day == day)
        row = self._session.execute(stmt).first()
        return (row.code, row.done_on) if row else None

    def choose(self, owner_id: int, day: date, code: str) -> None:
        """Записать выбор; в этот день он один — повтор отклоняется базой."""
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(daily_picks_table).values(
                        owner_id=owner_id, day=day, code=code, created_at=_now()
                    )
                )
        except IntegrityError:
            raise DailyDoneTodayError from None

    def mark_done(self, owner_id: int, day: date) -> bool:
        """Отметить выполнение; False — выбора на день ещё нет или уже отмечено."""
        t = daily_picks_table
        stmt = (
            t.update()
            .where(t.c.owner_id == owner_id, t.c.day == day, t.c.done_on.is_(None))
            .values(done_on=day)
        )
        return self._session.execute(stmt).rowcount == 1
