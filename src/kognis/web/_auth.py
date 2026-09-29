"""Вход, регистрация, выход, текущий пользователь (сессия — cookie, ADR 0003)."""

import datetime as dt
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.users import (
    DEFAULT_TIMEZONE,
    SESSION_LIFETIME,
    EmailTakenError,
    InvalidCredentialsError,
    LoginBlockedError,
    User,
    UserService,
)

from ._deps import COOKIE, Authed


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class RegisterIn(Credentials):
    # IANA-пояс из браузера; без него — пояс по умолчанию
    timezone: str | None = Field(default=None, max_length=64)


class UserOut(BaseModel):
    id: int
    email: str
    advanced: bool = False
    timezone: str = DEFAULT_TIMEZONE
    today: dt.date


def user_out(user: User, today: dt.date) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, advanced=user.advanced, timezone=user.timezone, today=today
    )


def auth_router(db: Engine, secure_cookie: bool, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter()

    def open_session(response: Response, user: User) -> None:
        with transaction(db) as session:
            token = UserService(session).start_session(user.id)
        response.set_cookie(
            COOKIE,
            token,
            max_age=int(SESSION_LIFETIME.total_seconds()),
            httponly=True,
            samesite="lax",
            secure=secure_cookie,
        )

    @router.post("/api/auth/register", status_code=201)
    def register(payload: RegisterIn, response: Response) -> UserOut:
        try:
            with transaction(db) as session:
                user = UserService(session).register(
                    payload.email, payload.password, payload.timezone
                )
        except EmailTakenError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        open_session(response, user)
        return user_out(user, today(user))

    @router.post("/api/auth/login")
    def login(payload: Credentials, request: Request, response: Response) -> UserOut:
        ip = request.client.host if request.client else "unknown"
        try:
            # попытка учитывается ДО проверки пароля (argon2 долгий): параллельная пачка запросов
            # не получит лишних попыток; успех ниже сбрасывает счётчик email
            with transaction(db) as session:
                service = UserService(session)
                service.ensure_login_allowed(payload.email, ip)
                service.record_login_failure(payload.email, ip)
        except LoginBlockedError as err:
            raise HTTPException(
                status_code=429, detail=str(err), headers={"Retry-After": str(err.retry_after)}
            ) from err
        try:
            with transaction(db) as session:
                user = UserService(session).authenticate(payload.email, payload.password)
        except InvalidCredentialsError as err:
            raise HTTPException(status_code=401, detail=str(err)) from err
        with transaction(db) as session:
            UserService(session).clear_login_failures(payload.email)
        open_session(response, user)
        return user_out(user, today(user))

    @router.post("/api/auth/logout", status_code=204)
    def logout(
        response: Response, token: Annotated[str | None, Cookie(alias=COOKIE)] = None
    ) -> None:
        if token:
            with transaction(db) as session:
                UserService(session).end_session(token)
        response.delete_cookie(COOKIE)

    @router.get("/api/me")
    def me(user: Authed) -> UserOut:
        return user_out(user, today(user))

    return router
