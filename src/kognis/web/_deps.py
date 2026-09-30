"""Общие зависимости роутеров: текущий пользователь, CSRF-проверка, «сегодня», блок помощи."""

import datetime as dt
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import Cookie, Depends, Request
from pydantic import BaseModel, Field

from kognis.db import transaction
from kognis.safety import HelpBlock
from kognis.users import User, UserService

from ._errors import http_error

COOKIE = "kognis_session"


def today_in(timezone: str, now: dt.datetime) -> dt.date:
    """«Сегодня» пользователя: дата в его поясе — единый источник для серий, квестов, периодов."""
    return now.astimezone(ZoneInfo(timezone)).date()


# Лимиты ввода (API4): границы совпадают с доменными, но срабатывают до обработки
Label = Annotated[str, Field(max_length=50)]
# постраничные списки: тело — обычный массив, курсор следующей страницы — в заголовке
NEXT_CURSOR_HEADER = "X-Next-Cursor"
Answer = Annotated[str, Field(max_length=2_000)]

# отметки рефлексии: ставит сам пользователь (маленький шаг, хорошее, переформулировка, инсайт)
Mark = Literal["step", "good", "reframe", "insight"]


class ContactOut(BaseModel):
    name: str
    phone: str
    note: str


class HelpOut(BaseModel):
    message: str
    contacts: list[ContactOut]


def help_out(block: HelpBlock | None) -> HelpOut | None:
    if block is None:
        return None
    contacts = [ContactOut(name=c.name, phone=c.phone, note=c.note) for c in block.contacts]
    return HelpOut(message=block.message, contacts=contacts)


def require_json(request: Request) -> None:
    """CSRF (ADR 0003): изменяющие запросы принимаются только как application/json."""
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.headers.get(
        "content-type", ""
    ).startswith("application/json"):
        raise http_error(415, "http.json_required")


def current_user(
    request: Request, token: Annotated[str | None, Cookie(alias=COOKIE)] = None
) -> User:
    if token:
        with transaction(request.app.state.db) as session:
            user = UserService(session).user_for_token(token)
        if user:
            return user
    raise http_error(401, "auth.required")


Authed = Annotated[User, Depends(current_user)]
