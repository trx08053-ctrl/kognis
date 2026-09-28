"""FastAPI-приложение. Модули вызываются только через публичный API (`kognis.users`).

Интерфейс — React (frontend/, сборка в frontend/dist); здесь только HTTP API и раздача сборки.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from kognis.db import make_engine, transaction
from kognis.users import User, UserService

HERE = Path(__file__).resolve().parent
# сборка фронтенда: <корень проекта>/frontend/dist (в образе — /app/frontend/dist)
DIST = Path(os.environ.get("FRONTEND_DIST", HERE.parents[2] / "frontend" / "dist"))


class UserIn(BaseModel):
    name: str


class UserOut(BaseModel):
    id: int
    name: str


def to_out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name)


def create_app(engine: Engine | None = None, frontend_dist: Path | None = None) -> FastAPI:
    db = engine or make_engine()
    dist = frontend_dist or DIST
    app = FastAPI(title="Kognis")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/users")
    def list_users() -> list[UserOut]:
        with transaction(db) as session:
            return [to_out(u) for u in UserService(session).list_all()]

    @app.post("/api/users", status_code=201)
    def create_user(payload: UserIn) -> UserOut:
        try:
            with transaction(db) as session:
                return to_out(UserService(session).register(payload.name))
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err

    @app.get("/")
    def index() -> Response:
        page = dist / "index.html"
        if not page.exists():
            return PlainTextResponse(
                "интерфейс не собран: pnpm --dir frontend build", status_code=503
            )
        return FileResponse(page)

    app.mount("/assets", StaticFiles(directory=dist / "assets", check_dir=False), name="assets")
    return app
