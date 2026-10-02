"""Хранение искр: журнал начислений и покупок (таблицы принадлежат модулю gameplay).

Баланс не хранится — вычисляется суммой журнала, как серия из дат активности: любое
начисление идемпотентно уникальностью (owner, kind, ref), покупка — уникальностью
(owner, item, ref). Отрицательным баланс быть не может: списание только покупкой.
"""

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
    inspect,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.db import metadata
from kognis.errors import CodedError

from ._sparks import ITEM_FREEZE


def _now() -> datetime:
    """Отметка времени записи (UTC без пояса — так хранит SQLite)."""
    return datetime.now(UTC).replace(tzinfo=None)


class NotEnoughSparksError(CodedError):
    """Баланса не хватает на покупку."""

    def __init__(self) -> None:
        super().__init__("sparks.not_enough")


class OwnedItemError(CodedError):
    """Товар с этим ref уже куплен: повторная покупка не списывает искры."""

    def __init__(self) -> None:
        super().__init__("sparks.owned")


spark_events_table = Table(
    "spark_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # владелец — id пользователя из users (без внешнего ключа: таблицей users владеет другой модуль)
    Column("owner_id", Integer, nullable=False, index=True),
    Column("kind", String(32), nullable=False),
    # источник (неделя, код достижения, id квеста): повторное начисление невозможно
    Column("ref", String(64), nullable=False),
    Column("day", Date, nullable=False),
    Column("amount", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "kind", "ref", name="uq_spark_events_owner_kind_ref"),
)

spark_purchases_table = Table(
    "spark_purchases",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, nullable=False, index=True),
    # код товара из каталога (_sparks.SHOP); ref = «once» у косметики, ISO-неделя у заморозки
    Column("item", String(32), nullable=False),
    Column("ref", String(64), nullable=False),
    Column("price", Integer, nullable=False),
    Column("day", Date, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("owner_id", "item", "ref", name="uq_spark_purchases_owner_item_ref"),
)


class SparkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._has_purchases: bool | None = None

    def add_spark_once(self, owner_id: int, kind: str, ref: str, day: date, amount: int) -> None:
        """Записать начисление; параллельный запрос с тем же источником ничего не добавляет."""
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(spark_events_table).values(
                        owner_id=owner_id,
                        kind=kind,
                        ref=ref,
                        day=day,
                        amount=amount,
                        created_at=_now(),
                    )
                )
        except IntegrityError:
            return

    def earned(self, owner_id: int) -> int:
        t = spark_events_table
        stmt = select(func.coalesce(func.sum(t.c.amount), 0)).where(t.c.owner_id == owner_id)
        return int(self._session.execute(stmt).scalar_one())

    def spent(self, owner_id: int) -> int:
        t = spark_purchases_table
        stmt = select(func.coalesce(func.sum(t.c.price), 0)).where(t.c.owner_id == owner_id)
        return int(self._session.execute(stmt).scalar_one())

    def balance(self, owner_id: int) -> int:
        return self.earned(owner_id) - self.spent(owner_id)

    def purchases(self, owner_id: int) -> list[tuple[str, str, date]]:
        """(товар, ref, дата) — какие покупки у владельца."""
        t = spark_purchases_table
        stmt = select(t.c.item, t.c.ref, t.c.day).where(t.c.owner_id == owner_id).order_by(t.c.id)
        return [(r.item, r.ref, r.day) for r in self._session.execute(stmt).all()]

    def has_purchase(self, owner_id: int, item: str, ref: str) -> bool:
        t = spark_purchases_table
        stmt = select(t.c.id).where(t.c.owner_id == owner_id, t.c.item == item, t.c.ref == ref)
        return self._session.execute(stmt).first() is not None

    def add_purchase(self, owner_id: int, item: str, ref: str, price: int, day: date) -> None:
        """Списать искры за покупку; уже купленное с этим ref — ошибка без списания.

        Владение проверяется раньше баланса: «уже куплено» точнее «не хватает».
        Проверка баланса и списание в одной транзакции держат неотрицательность баланса;
        на Postgres покупки одного владельца сериализует advisory-лок (READ COMMITTED
        иначе допустил бы два списания одного баланса), SQLite пишет только один.
        """
        self._lock_owner(owner_id)
        if self.has_purchase(owner_id, item, ref):
            raise OwnedItemError
        if self.balance(owner_id) < price:
            raise NotEnoughSparksError
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(spark_purchases_table).values(
                        owner_id=owner_id,
                        item=item,
                        ref=ref,
                        price=price,
                        day=day,
                        created_at=_now(),
                    )
                )
        except IntegrityError:
            raise OwnedItemError from None

    def _lock_owner(self, owner_id: int) -> None:
        """Покупки одного владельца — по очереди (миграции проверок не требует)."""
        if self._session.get_bind().dialect.name == "postgresql":
            self._session.execute(text("SELECT pg_advisory_xact_lock(:owner)"), {"owner": owner_id})

    def freeze_days(self, owner_id: int) -> frozenset[date]:
        """Дни покупки заморозок: запас серии пополняется в эти даты (кап в _streak).

        Expand: на схеме до 0019 таблицы ещё нет (код деплоится раньше миграции) —
        покупок не бывает, серия считается без них.
        """
        if self._has_purchases is None:
            self._has_purchases = inspect(self._session.get_bind()).has_table("spark_purchases")
        if not self._has_purchases:
            return frozenset()
        t = spark_purchases_table
        stmt = select(t.c.day).where(t.c.owner_id == owner_id, t.c.item == ITEM_FREEZE)
        rows = self._session.execute(stmt).all()
        return frozenset(r.day for r in rows)
