"""Прогресс: опыт, уровень, серия, достижения."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import (
    GameplayService,
    Progress,
)
from kognis.users import (
    User,
)

from ._deps import Authed


class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    earned_on: dt.date


class ProgressOut(BaseModel):
    xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    streak: int
    achievements: list[AchievementOut]


def progress_out(progress: Progress) -> ProgressOut:
    return ProgressOut(
        xp=progress.xp,
        level=progress.level,
        level_start_xp=progress.level_start_xp,
        next_level_xp=progress.next_level_xp,
        streak=progress.streak,
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

    return router
