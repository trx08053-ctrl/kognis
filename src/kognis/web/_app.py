"""FastAPI-приложение: только сборка. Роутеры — по файлу на область (`_auth.py`, `_diary.py` …).

Модули вызываются только через публичный API (`users`, `diary` …).
Интерфейс — React (frontend/, сборка в frontend/dist); здесь только HTTP API и раздача сборки.
Сессия — cookie `kognis_session` (httpOnly, SameSite=Lax), ADR 0003. Содержимое записей не логируем.
"""

import datetime as dt
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.engine import Engine

from kognis.ai import AiProvider, get_provider
from kognis.db import make_engine
from kognis.users import User

from ._analysis import analysis_router
from ._auth import auth_router
from ._deps import require_json, today_in
from ._diary import diary_router
from ._errors import error_detail, http_error
from ._limits import BodyLimitMiddleware
from ._progress import progress_router
from ._quests import quests_router
from ._quizzes import quizzes_router
from ._reviews import day_review_router
from ._settings import settings_router

HERE = Path(__file__).resolve().parent
# сборка фронтенда: <корень проекта>/frontend/dist (в образе — /app/frontend/dist)
DIST = Path(os.environ.get("FRONTEND_DIST", HERE.parents[2] / "frontend" / "dist"))
# Интерфейс — своя сборка без inline-скриптов/стилей и внешних ресурсов, поэтому CSP строгий
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
DOC_PATHS = ("docs", "redoc", "openapi.json")  # документация API — только в dev
HSTS = "max-age=31536000; includeSubDomains"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def create_app(
    engine: Engine | None = None,
    frontend_dist: Path | None = None,
    clock: Callable[[], dt.datetime] = utc_now,
    ai_provider: AiProvider | None = None,
    data_key: str | None = None,
) -> FastAPI:
    """`clock` — текущее время с поясом; «сегодня» считается из него по поясу пользователя."""

    def user_today(user: User) -> dt.date:
        return today_in(user.timezone, clock())

    db = engine or make_engine()
    # ключ данных для записей «под замком» (D4): base64, 32 байта; без него замок недоступен
    data_key = data_key or os.environ.get("KOGNIS_DATA_KEY")
    dist = frontend_dist or DIST
    # Secure по умолчанию; отключается только явным KOGNIS_ENV=dev (ADR 0003)
    secure_cookie = os.environ.get("KOGNIS_ENV") != "dev"
    is_dev = not secure_cookie
    # вне dev документации нет; схема доступна коду напрямую: app.openapi() (gen_api_types.py)
    app = FastAPI(
        title="Kognis",
        dependencies=[Depends(require_json)],
        docs_url="/docs" if is_dev else None,
        redoc_url="/redoc" if is_dev else None,
        openapi_url="/openapi.json" if is_dev else None,
    )
    app.state.db = db
    app.add_middleware(BodyLimitMiddleware)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        # ASVS V7: наружу — только общий текст, без трассировки и деталей исключения
        return JSONResponse(
            {"detail": error_detail("server.internal")},
            status_code=500,
            headers=SECURITY_HEADERS,
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[..., Any]) -> Response:
        response: Response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if secure_cookie:  # HSTS только там, где работает https (не в dev по http)
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/health")
    def health() -> Response:
        try:
            with db.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            logging.getLogger(__name__).error("health: db unavailable (%s)", type(exc).__name__)
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    app.include_router(auth_router(db, secure_cookie, user_today))
    app.include_router(settings_router(db, user_today))
    app.include_router(diary_router(db, user_today, data_key))
    app.include_router(day_review_router(db, user_today))
    app.include_router(progress_router(db, user_today))
    provider = ai_provider or get_provider()
    app.include_router(analysis_router(db, provider))
    app.include_router(quests_router(db, user_today, provider))
    app.include_router(quizzes_router(db, user_today))
    app.mount("/assets", StaticFiles(directory=dist / "assets", check_dir=False), name="assets")

    @app.get("/{path:path}")
    def index(path: str) -> Response:
        """Любой путь вне /api — страница SPA (маршруты разбирает React Router)."""
        if path.startswith("api/") or (not is_dev and path in DOC_PATHS):
            raise http_error(404, "http.not_found")
        page = dist / "index.html"
        if not page.exists():
            return PlainTextResponse(
                "frontend is not built: pnpm --dir frontend build", status_code=503
            )
        return FileResponse(page)

    return app
