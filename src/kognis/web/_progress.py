"""Прогресс: опыт, уровень, серия, достижения."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import (
    GameplayService,
    Progress,
    RecoveryUnavailableError,
)
from kognis.users import (
    User,
)

from ._deps import Authed
from ._errors import http_error


class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    earned_on: dt.date


class RecoveryOfferOut(BaseModel):
    streak_before: int
    broken_on: dt.date
    expires_on: dt.date


class ProgressOut(BaseModel):
    xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    streak: int
    best_streak: int
    freezes: int
    days_30: int
    days_total: int
    weekly_goal: int
    week_days: int
    weekend_days: list[int]
    recovery: RecoveryOfferOut | None
    achievements: list[AchievementOut]


class SettingsIn(BaseModel):
    weekend_days: list[int] = Field(max_length=7)
    weekly_goal: int


class RecoveryIn(BaseModel):
    note: str = Field(min_length=1, max_length=500, pattern=r"\S")


def progress_out(progress: Progress) -> ProgressOut:
    offer = progress.recovery
    return ProgressOut(
        xp=progress.xp,
        level=progress.level,
        level_start_xp=progress.level_start_xp,
        next_level_xp=progress.next_level_xp,
        streak=progress.streak,
        best_streak=progress.best_streak,
        freezes=progress.freezes,
        days_30=progress.days_30,
        days_total=progress.days_total,
        weekly_goal=progress.weekly_goal,
        week_days=progress.week_days,
        weekend_days=list(progress.weekend_days),
        recovery=RecoveryOfferOut(
            streak_before=offer.streak_before,
            broken_on=offer.broken_on,
            expires_on=offer.expires_on,
        )
        if offer
        else None,
        achievements=[
            AchievementOut(
                code=a.code, title=a.title, description=a.description, earned_on=a.earned_on
            )
            for a in progress.achievements
        ],
    )


def progress_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/progress")

    @router.get("")
    def get_progress(user: Authed) -> ProgressOut:
        with transaction(db) as session:
            return progress_out(GameplayService(session).progress(user.id, today(user)))

    @router.put("/settings")
    def put_settings(payload: SettingsIn, user: Authed) -> ProgressOut:
        """Выходные дни и недельная цель — выбор пользователя."""
        try:
            with transaction(db) as session:
                service = GameplayService(session)
                return progress_out(
                    service.save_settings(
                        user.id, payload.weekend_days, payload.weekly_goal, today(user)
                    )
                )
        except ValueError as err:
            raise http_error(422, err) from err

    @router.post("/recovery")
    def post_recovery(payload: RecoveryIn, user: Authed) -> ProgressOut:
        """Вернуть оборванную серию: «что помешало», одна запись на обрыв, в течение 72 часов."""
        try:
            with transaction(db) as session:
                return progress_out(
                    GameplayService(session).recover(user.id, payload.note, today(user))
                )
        except RecoveryUnavailableError as err:
            raise http_error(409, err) from err

    return router
