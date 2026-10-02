"""Квест дня: три лёгких задания на выбор, без штрафа за невыполнение (kognis-crn)."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import DailyDoneTodayError, DailyState, QuestService
from kognis.users import User

from ._deps import Authed
from ._errors import http_error


class DailyOut(BaseModel):
    options: list[str]  # коды заданий; тексты — интерфейс, по словарю `daily.<code>`
    picked: str | None
    done: bool
    weekly: str | None  # квест недели от наставника (принимается обычным POST /api/quests)


class DailyChooseIn(BaseModel):
    code: str = Field(max_length=32)


def daily_out(state: DailyState, weekly: str | None) -> DailyOut:
    return DailyOut(
        options=list(state.options), picked=state.picked, done=state.done, weekly=weekly
    )


def daily_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/daily-quest")

    @router.get("")
    def get_daily(user: Authed) -> DailyOut:
        """Задание дня: три варианта и квест недели от наставника."""
        with transaction(db) as session:
            service = QuestService(session)
            return daily_out(
                service.daily(user.id, today(user)), service.weekly(user.id, today(user))
            )

    @router.post("/choose")
    def choose_daily(payload: DailyChooseIn, user: Authed) -> DailyOut:
        """Выбрать одно из трёх заданий; в этот день выбор один."""
        try:
            with transaction(db) as session:
                service = QuestService(session)
                service.choose_daily(user.id, payload.code, today(user))
                return daily_out(
                    service.daily(user.id, today(user)), service.weekly(user.id, today(user))
                )
        except DailyDoneTodayError as err:
            raise http_error(409, err) from err
        except ValueError as err:
            raise http_error(422, err) from err

    @router.post("/done")
    def complete_daily(user: Authed) -> DailyOut:
        """Отметить выбранное задание выполненным (+XP и искры один раз за день)."""
        try:
            with transaction(db) as session:
                service = QuestService(session)
                state = service.complete_daily(user.id, today(user))
                return daily_out(state, service.weekly(user.id, today(user)))
        except ValueError as err:  # на день выбора ещё нет
            raise http_error(422, err) from err

    return router
