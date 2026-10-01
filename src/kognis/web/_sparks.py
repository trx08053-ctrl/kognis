"""Искры: баланс, витрина и покупка (косметика спутника, темы дневника, заморозка)."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import (
    FreezeStockFullError,
    NotEnoughSparksError,
    OwnedItemError,
    SparksService,
    SparksState,
)
from kognis.users import User

from ._deps import Authed
from ._errors import http_error


class ShopPositionOut(BaseModel):
    code: str
    kind: str
    price: int
    owned: bool


class SparksOut(BaseModel):
    balance: int
    freezes: int
    catalog: list[ShopPositionOut]


class PurchaseIn(BaseModel):
    item: str = Field(max_length=32)


def sparks_out(state: SparksState) -> SparksOut:
    return SparksOut(
        balance=state.balance,
        freezes=state.freezes,
        catalog=[
            ShopPositionOut(code=p.code, kind=p.kind, price=p.price, owned=p.owned)
            for p in state.catalog
        ],
    )


def sparks_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/sparks")

    @router.get("")
    def get_sparks(user: Authed) -> SparksOut:
        with transaction(db) as session:
            return sparks_out(SparksService(session).state(user.id, today(user)))

    @router.post("/purchase")
    def post_purchase(payload: PurchaseIn, user: Authed) -> SparksOut:
        """Купить товар каталога: уже купленное и нехватка баланса — 409 с кодом."""
        try:
            with transaction(db) as session:
                state = SparksService(session).purchase(user.id, payload.item, today(user))
        except NotEnoughSparksError as err:
            raise http_error(409, err) from err
        except OwnedItemError as err:
            raise http_error(409, err) from err
        except FreezeStockFullError as err:
            raise http_error(409, err) from err
        except ValueError as err:  # неизвестный товар
            raise http_error(422, err) from err
        return sparks_out(state)

    return router
