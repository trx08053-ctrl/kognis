"""Настройки пользователя."""

import datetime as dt
from collections.abc import Callable
from dataclasses import replace

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.users import (
    MAX_LOCALE_LENGTH,
    User,
    UserService,
)

from ._auth import UserOut, user_out
from ._deps import Authed
from ._errors import http_error


class SettingsIn(BaseModel):
    advanced: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=MAX_LOCALE_LENGTH)


def settings_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/me/settings")

    @router.put("")
    def save_settings(payload: SettingsIn, user: Authed) -> UserOut:
        if payload.advanced is None and payload.timezone is None and payload.locale is None:
            raise http_error(422, "settings.empty")
        try:
            with transaction(db) as session:
                service = UserService(session)
                if payload.advanced is not None:
                    service.set_advanced(user.id, payload.advanced)
                    user = replace(user, advanced=payload.advanced)
                if payload.timezone is not None:
                    service.set_timezone(user.id, payload.timezone)
                    user = replace(user, timezone=payload.timezone)
                if payload.locale is not None:
                    service.set_locale(user.id, payload.locale)
                    user = replace(user, locale=payload.locale)
        except ValueError as err:
            raise http_error(422, err) from err
        return user_out(user, today(user))

    return router
