"""FastAPI-приложение. Модули вызываются только через публичный API (`users`, `diary`).

Интерфейс — React (frontend/, сборка в frontend/dist); здесь только HTTP API и раздача сборки.
Сессия — cookie `kognis_session` (httpOnly, SameSite=Lax), ADR 0003. Содержимое записей не логируем.
"""

import datetime as dt
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from kognis.db import make_engine, transaction
from kognis.diary import DayReview, DiaryService, Entry
from kognis.users import (
    SESSION_LIFETIME,
    EmailTakenError,
    InvalidCredentialsError,
    User,
    UserService,
)

HERE = Path(__file__).resolve().parent
# сборка фронтенда: <корень проекта>/frontend/dist (в образе — /app/frontend/dist)
DIST = Path(os.environ.get("FRONTEND_DIST", HERE.parents[2] / "frontend" / "dist"))
COOKIE = "kognis_session"


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class UserOut(BaseModel):
    id: int
    email: str


class EntryIn(BaseModel):
    text: str
    tags: list[str] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    date: dt.date | None = None


class EntryOut(BaseModel):
    id: int
    date: dt.date
    text: str
    tags: list[str]
    emotions: list[str]
    protection: str


class DayReviewIn(BaseModel):
    wellbeing: StrictInt
    mood: StrictInt
    reflection: str = ""


class DayReviewOut(BaseModel):
    id: int
    date: dt.date
    wellbeing: int
    mood: int
    reflection: str


def review_out(review: DayReview) -> DayReviewOut:
    return DayReviewOut(
        id=review.id,
        date=review.review_date,
        wellbeing=review.wellbeing,
        mood=review.mood,
        reflection=review.reflection,
    )


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email)


def entry_out(entry: Entry) -> EntryOut:
    return EntryOut(
        id=entry.id,
        date=entry.entry_date,
        text=entry.text,
        tags=list(entry.tags),
        emotions=list(entry.emotions),
        protection=entry.protection,
    )


def require_json(request: Request) -> None:
    """CSRF (ADR 0003): изменяющие запросы принимаются только как application/json."""
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.headers.get(
        "content-type", ""
    ).startswith("application/json"):
        raise HTTPException(status_code=415, detail="нужен Content-Type: application/json")


def current_user(
    request: Request, token: Annotated[str | None, Cookie(alias=COOKIE)] = None
) -> User:
    if token:
        with transaction(request.app.state.db) as session:
            user = UserService(session).user_for_token(token)
        if user:
            return user
    raise HTTPException(status_code=401, detail="нужен вход")


Authed = Annotated[User, Depends(current_user)]


def diary_router(db: Engine) -> APIRouter:
    router = APIRouter(prefix="/api/entries")

    @router.post("", status_code=201)
    def create_entry(payload: EntryIn, user: Authed) -> EntryOut:
        try:
            with transaction(db) as session:
                entry = DiaryService(session).create_entry(
                    user.id, payload.text, payload.tags, payload.emotions, payload.date
                )
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return entry_out(entry)

    @router.get("")
    def list_entries(user: Authed) -> list[EntryOut]:
        with transaction(db) as session:
            return [entry_out(e) for e in DiaryService(session).list_entries(user.id)]

    @router.get("/{entry_id}")
    def get_entry(entry_id: int, user: Authed) -> EntryOut:
        with transaction(db) as session:
            entry = DiaryService(session).get_entry(user.id, entry_id)
        if entry is None:  # чужая запись неотличима от несуществующей
            raise HTTPException(status_code=404, detail="запись не найдена")
        return entry_out(entry)

    return router


def day_review_router(db: Engine) -> APIRouter:
    router = APIRouter(prefix="/api/day-reviews")

    @router.put("/{review_date}")
    def save_review(review_date: dt.date, payload: DayReviewIn, user: Authed) -> DayReviewOut:
        def save() -> DayReview:
            with transaction(db) as session:
                return DiaryService(session).save_day_review(
                    user.id, review_date, payload.wellbeing, payload.mood, payload.reflection
                )

        try:
            try:
                review = save()
            except IntegrityError:
                # два одновременных сохранения за один день: проигравший (уникальность держит БД)
                # повторяет и обновляет уже существующий итог
                review = save()
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return review_out(review)

    @router.get("")
    def list_reviews(user: Authed) -> list[DayReviewOut]:
        with transaction(db) as session:
            return [review_out(r) for r in DiaryService(session).list_day_reviews(user.id)]

    return router


def create_app(engine: Engine | None = None, frontend_dist: Path | None = None) -> FastAPI:
    db = engine or make_engine()
    dist = frontend_dist or DIST
    # Secure по умолчанию; отключается только явным KOGNIS_ENV=dev (ADR 0003)
    secure_cookie = os.environ.get("KOGNIS_ENV") != "dev"
    app = FastAPI(title="Kognis", dependencies=[Depends(require_json)])
    app.state.db = db

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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/register", status_code=201)
    def register(payload: Credentials, response: Response) -> UserOut:
        try:
            with transaction(db) as session:
                user = UserService(session).register(payload.email, payload.password)
        except EmailTakenError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        open_session(response, user)
        return user_out(user)

    @app.post("/api/auth/login")
    def login(payload: Credentials, response: Response) -> UserOut:
        try:
            with transaction(db) as session:
                user = UserService(session).authenticate(payload.email, payload.password)
        except InvalidCredentialsError as err:
            raise HTTPException(status_code=401, detail=str(err)) from err
        open_session(response, user)
        return user_out(user)

    @app.post("/api/auth/logout", status_code=204)
    def logout(
        response: Response, token: Annotated[str | None, Cookie(alias=COOKIE)] = None
    ) -> None:
        if token:
            with transaction(db) as session:
                UserService(session).end_session(token)
        response.delete_cookie(COOKIE)

    @app.get("/api/me")
    def me(user: Authed) -> UserOut:
        return user_out(user)

    app.include_router(diary_router(db))
    app.include_router(day_review_router(db))
    app.mount("/assets", StaticFiles(directory=dist / "assets", check_dir=False), name="assets")

    @app.get("/{path:path}")
    def index(path: str) -> Response:
        """Любой путь вне /api — страница SPA (маршруты разбирает React Router)."""
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="не найдено")
        page = dist / "index.html"
        if not page.exists():
            return PlainTextResponse(
                "интерфейс не собран: pnpm --dir frontend build", status_code=503
            )
        return FileResponse(page)

    return app
