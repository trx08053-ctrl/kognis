"""Настройки пользователя."""

import datetime as dt
from collections.abc import Callable
from dataclasses import replace

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.users import (
    User,
    UserService,
)

from ._auth import UserOut, user_out
from ._deps import Authed


class SettingsIn(BaseModel):
    advanced: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)


def settings_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/me/settings")

    @router.put("")
    def save_settings(payload: SettingsIn, user: Authed) -> UserOut:
        if payload.advanced is None and payload.timezone is None:
            raise HTTPException(status_code=422, detail="нечего сохранять")
        try:
            with transaction(db) as session:
                service = UserService(session)
                if payload.advanced is not None:
                    service.set_advanced(user.id, payload.advanced)
                    user = replace(user, advanced=payload.advanced)
                if payload.timezone is not None:
                    service.set_timezone(user.id, payload.timezone)
                    user = replace(user, timezone=payload.timezone)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return user_out(user, today(user))

    return router
