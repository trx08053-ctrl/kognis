"""Хранение прогресса (таблицы `xp_events` и `achievements` принадлежат модулю gameplay)."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import KIND_REFLECTION

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
    # отметки рефлексии через запятую (только у событий `reflection`)
    Column("marks", String(32), nullable=True),
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

gameplay_settings_table = Table(
    "gameplay_settings",
    metadata,
    Column("owner_id", Integer, primary_key=True, autoincrement=False),
    Column("weekend_days", String(16), nullable=False, default=""),  # «5,6» — дни недели, 0 — пн
    Column("weekly_goal", Integer, nullable=False, default=3),
    Column("rules_from", Date, nullable=True),  # до этой даты — прежнее правило заморозки
)

streak_recoveries_table = Table(
    "streak_recoveries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False),
    Column("after_day", Date, nullable=False),  # последняя активность перед восстановленным обрывом
    Column("broken_on", Date, nullable=False),
    Column("note", Text, nullable=False),  # «что помешало» — видит только владелец
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "after_day", name="uq_streak_recoveries_owner_after"),
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

    def add_event_once(self, owner_id: int, kind: str, ref: str, day: date, xp: int) -> None:
        """Записать событие XP; если параллельный запрос успел раньше — тихо ничего не делать.

        Savepoint не даёт конфликту откатить всю транзакцию (вместе с записью дневника).
        """
        try:
            with self._session.begin_nested():
                self.add_event(owner_id, kind, ref, day, xp)
        except IntegrityError:
            return

    def add_reflection_once(self, owner_id: int, ref: str, day: date, xp: int, marks: str) -> None:
        """Бонус рефлексии с отметками (для достижений «Глубины»); повтор тихо игнорируется."""
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(xp_events_table).values(
                        owner_id=owner_id,
                        kind=KIND_REFLECTION,
                        ref=ref,
                        day=day,
                        xp=xp,
                        marks=marks,
                        created_at=_now(),
                    )
                )
        except IntegrityError:
            return

    def xp_on_day(self, owner_id: int, kinds: tuple[str, ...], day: date) -> int:
        t = xp_events_table
        stmt = select(func.coalesce(func.sum(t.c.xp), 0)).where(
            t.c.owner_id == owner_id, t.c.kind.in_(kinds), t.c.day == day
        )
        return int(self._session.execute(stmt).scalar_one())

    def refs(self, owner_id: int, kind: str) -> list[str]:
        t = xp_events_table
        stmt = select(t.c.ref).where(t.c.owner_id == owner_id, t.c.kind == kind)
        return [r.ref for r in self._session.execute(stmt).all()]

    def reflection_marks(self, owner_id: int) -> list[frozenset[str]]:
        """Отметки каждой рефлексии владельца (события с бонусом или без него)."""
        t = xp_events_table
        stmt = select(t.c.marks).where(t.c.owner_id == owner_id, t.c.kind == KIND_REFLECTION)
        rows = self._session.execute(stmt).all()
        return [frozenset((r.marks or "").split(",")) - {""} for r in rows]

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

    def settings(self, owner_id: int) -> tuple[frozenset[int], int, date | None] | None:
        """(выходные дни, недельная цель, `rules_from`) или None, если настроек ещё нет."""
        t = gameplay_settings_table
        stmt = select(t.c.weekend_days, t.c.weekly_goal, t.c.rules_from).where(
            t.c.owner_id == owner_id
        )
        row = self._session.execute(stmt).first()
        if row is None:
            return None
        weekend = frozenset(int(x) for x in row.weekend_days.split(",") if x)
        return weekend, row.weekly_goal, row.rules_from

    def save_settings(self, owner_id: int, weekend_days: frozenset[int], weekly_goal: int) -> None:
        """Сохранить выбор пользователя; `rules_from` (переход на новые правила) не трогаем."""
        t = gameplay_settings_table
        csv = ",".join(str(d) for d in sorted(weekend_days))
        if self.settings(owner_id) is not None:
            self._update_settings(owner_id, csv, weekly_goal)
            return
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(t).values(owner_id=owner_id, weekend_days=csv, weekly_goal=weekly_goal)
                )
        except IntegrityError:  # параллельный первый PUT успел раньше
            self._update_settings(owner_id, csv, weekly_goal)

    def _update_settings(self, owner_id: int, csv: str, weekly_goal: int) -> None:
        t = gameplay_settings_table
        self._session.execute(
            update(t)
            .where(t.c.owner_id == owner_id)
            .values(weekend_days=csv, weekly_goal=weekly_goal)
        )

    def recovered_after_days(self, owner_id: int) -> frozenset[date]:
        t = streak_recoveries_table
        rows = self._session.execute(select(t.c.after_day).where(t.c.owner_id == owner_id)).all()
        return frozenset(r.after_day for r in rows)

    def add_recovery(self, owner_id: int, after_day: date, broken_on: date, note: str) -> bool:
        """Записать восстановление; False, если этот обрыв уже восстановлен (одно на обрыв)."""
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(streak_recoveries_table).values(
                        owner_id=owner_id,
                        after_day=after_day,
                        broken_on=broken_on,
                        note=note,
                        created_at=_now(),
                    )
                )
        except IntegrityError:
            return False
        return True
