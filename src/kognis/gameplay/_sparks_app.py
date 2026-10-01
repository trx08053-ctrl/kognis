"""Сценарии искр: витрина магазина и покупка. Вызывает слой web (D2).

Принципы ADR 0006: валюта не продаёт прогресс, разборы и аналитику — только косметика
и заморозка; запас заморозок не бывает больше двух и «пустых» покупок не происходит:
при полном запасе покупка заморозки отклоняется.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from kognis.errors import CodedError, CodedValueError

from ._app import GameplayService
from ._sparks import (
    ITEM_FREEZE,
    SHOP,
    ShopItem,
    item_by_code,
    purchase_ref,
)
from ._sparks_infra import NotEnoughSparksError, OwnedItemError, SparkRepository
from ._streak import FREEZE_STOCK_MAX


class FreezeStockFullError(CodedError):
    """Запас заморозок уже полный: покупать ещё одну бессмысленно."""

    def __init__(self) -> None:
        super().__init__("sparks.freeze_full", max=FREEZE_STOCK_MAX)


@dataclass(frozen=True)
class ShopPosition:
    code: str
    kind: str
    price: int
    owned: bool  # куплено с текущим ref (косметика — навсегда, заморозка — на эту неделю)


@dataclass(frozen=True)
class SparksState:
    balance: int
    freezes: int  # текущий запас заморозок серии
    catalog: tuple[ShopPosition, ...]


class SparksService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SparkRepository(session)

    def state(self, owner_id: int, today: date) -> SparksState:
        """Баланс, запас заморозок и витрина с отметкой купленного."""
        owned = {(item, ref) for item, ref, _ in self._repo.purchases(owner_id)}
        catalog = tuple(
            ShopPosition(
                entry.code,
                entry.kind,
                entry.price,
                (entry.code, purchase_ref(entry, today)) in owned,
            )
            for entry in SHOP
        )
        return SparksState(
            balance=self._repo.balance(owner_id),
            freezes=GameplayService(self._session).progress(owner_id, today).freezes,
            catalog=catalog,
        )

    def purchase(self, owner_id: int, code: str, today: date) -> SparksState:
        """Купить товар: косметика (навсегда) или заморозка (+1 к запасу, не выше двух)."""
        item = self._item(code)
        if item.kind == ITEM_FREEZE and self.state(owner_id, today).freezes >= FREEZE_STOCK_MAX:
            raise FreezeStockFullError  # не продаём бесполезное (без вины — просто «уже полный»)
        self._repo.add_purchase(owner_id, item.code, purchase_ref(item, today), item.price, today)
        return self.state(owner_id, today)

    def _item(self, code: str) -> ShopItem:
        try:
            return item_by_code(code)
        except KeyError as err:
            raise CodedValueError("sparks.item_unknown") from err


__all__ = [
    "FreezeStockFullError",
    "NotEnoughSparksError",
    "OwnedItemError",
    "ShopPosition",
    "SparksService",
    "SparksState",
]
