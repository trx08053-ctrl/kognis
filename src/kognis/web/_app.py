"""FastAPI-приложение. Модули вызываются только через публичный API (`users`, `diary`).

Интерфейс — React (frontend/, сборка в frontend/dist); здесь только HTTP API и раздача сборки.
Сессия — cookie `kognis_session` (httpOnly, SameSite=Lax), ADR 0003. Содержимое записей не логируем.
"""

import datetime as dt
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from kognis.access import Feature, can_use
from kognis.ai import AiProvider, get_provider
from kognis.analysis import (
    DIRECTIONS,
    Analysis,
    AnalysisFailedError,
    AnalysisOutcome,
    AnalysisService,
    ConsentRequiredError,
    MoodDynamics,
    NoDataError,
)
from kognis.db import make_engine, transaction
from kognis.diary import DayReview, DiaryService, Entry
from kognis.gameplay import GameplayService, Progress
from kognis.safety import HelpBlock, check_text
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
# часовой пояс профиля по умолчанию (D11); хранение своего пояса в профиле — отдельной задачей
DEFAULT_TZ = ZoneInfo("Europe/Moscow")


def local_today() -> dt.date:
    """Сегодняшняя дата пользователя — по ней считается серия дней."""
    return dt.datetime.now(DEFAULT_TZ).date()


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


class ContactOut(BaseModel):
    name: str
    phone: str
    note: str


class HelpOut(BaseModel):
    message: str
    contacts: list[ContactOut]


class EntryOut(BaseModel):
    id: int
    date: dt.date
    text: str
    tags: list[str]
    emotions: list[str]
    protection: str
    crisis: bool = False
    help: HelpOut | None = None


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
    help: HelpOut | None = None


def review_out(review: DayReview, block: HelpBlock | None = None) -> DayReviewOut:
    return DayReviewOut(
        id=review.id,
        date=review.review_date,
        wellbeing=review.wellbeing,
        mood=review.mood,
        reflection=review.reflection,
        help=help_out(block),
    )


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


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email)


def help_out(block: HelpBlock | None) -> HelpOut | None:
    if block is None:
        return None
    contacts = [ContactOut(name=c.name, phone=c.phone, note=c.note) for c in block.contacts]
    return HelpOut(message=block.message, contacts=contacts)


def entry_out(entry: Entry, block: HelpBlock | None = None) -> EntryOut:
    return EntryOut(
        id=entry.id,
        date=entry.entry_date,
        text=entry.text,
        tags=list(entry.tags),
        emotions=list(entry.emotions),
        protection=entry.protection,
        crisis=entry.crisis,
        help=help_out(block),
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


def diary_router(db: Engine, today: Callable[[], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/entries")

    @router.post("", status_code=201)
    def create_entry(payload: EntryIn, user: Authed) -> EntryOut:
        try:
            # кризисный сигнал ищем локально (safety); запись сохраняется всегда
            assessment, block = check_text(
                " | ".join([payload.text, *payload.tags, *payload.emotions])
            )
            with transaction(db) as session:
                diary = DiaryService(session)
                entry = diary.create_entry(
                    user.id, payload.text, payload.tags, payload.emotions, payload.date or today()
                )
                if not assessment.allows_rewards:
                    # кризисная запись опыта не даёт (D5)
                    entry = diary.mark_crisis(user.id, entry.id) or entry
                else:
                    GameplayService(session).award_entry(
                        user.id, entry.id, entry.entry_date, today()
                    )
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return entry_out(entry, block)

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


def day_review_router(db: Engine, today: Callable[[], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/day-reviews")

    @router.put("/{review_date}")
    def save_review(review_date: dt.date, payload: DayReviewIn, user: Authed) -> DayReviewOut:
        # рефлексию проверяем так же, как запись (TD-4); итог сохраняется всегда
        assessment, block = check_text(payload.reflection)

        def save() -> DayReview:
            with transaction(db) as session:
                review = DiaryService(session).save_day_review(
                    user.id, review_date, payload.wellbeing, payload.mood, payload.reflection
                )
                if assessment.allows_rewards:
                    GameplayService(session).award_day_review(user.id, review_date, today())
                return review

        try:
            try:
                review = save()
            except IntegrityError:
                # два одновременных сохранения за один день: проигравший (уникальность держит БД)
                # повторяет и обновляет уже существующий итог
                review = save()
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return review_out(review, block)

    @router.get("")
    def list_reviews(user: Authed) -> list[DayReviewOut]:
        with transaction(db) as session:
            return [review_out(r) for r in DiaryService(session).list_day_reviews(user.id)]

    return router


def progress_router(db: Engine, today: Callable[[], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/progress")

    @router.get("")
    def get_progress(user: Authed) -> ProgressOut:
        with transaction(db) as session:
            return progress_out(GameplayService(session).progress(user.id, today()))

    return router


class DirectionOut(BaseModel):
    code: str
    title: str


class AnalyzeIn(BaseModel):
    direction: str
    start: dt.date
    end: dt.date
    consent: bool = False


class AnswersIn(BaseModel):
    answers: list[str]
    consent: bool = False


class PatternOut(BaseModel):
    title: str
    description: str
    entry_ids: list[int]
    quotes: list[str]


class AnalysisOut(BaseModel):
    id: int
    parent_id: int | None
    direction: str
    start: dt.date
    end: dt.date
    status: str
    summary: str | None
    patterns: list[PatternOut]
    questions: list[str]
    quest_ideas: list[str]
    answers: list[str]
    help: HelpOut | None = None


class MoodPointOut(BaseModel):
    date: dt.date
    mood: int
    wellbeing: int


class MoodOut(BaseModel):
    points: list[MoodPointOut]
    average_mood: float | None
    average_wellbeing: float | None
    trend: str


def analysis_out(analysis: Analysis, block: HelpBlock | None = None) -> AnalysisOut:
    result = analysis.result
    return AnalysisOut(
        id=analysis.id,
        parent_id=analysis.parent_id,
        direction=analysis.direction,
        start=analysis.start,
        end=analysis.end,
        status=analysis.status,
        summary=result.summary if result else None,
        patterns=[PatternOut(**p.model_dump()) for p in result.patterns] if result else [],
        questions=result.questions if result else [],
        quest_ideas=result.quest_ideas if result else [],
        answers=list(analysis.answers),
        help=help_out(block),
    )


def outcome_out(outcome: AnalysisOutcome) -> AnalysisOut:
    return analysis_out(outcome.analysis, outcome.help)


def mood_out(mood: MoodDynamics) -> MoodOut:
    return MoodOut(
        points=[MoodPointOut(date=p.day, mood=p.mood, wellbeing=p.wellbeing) for p in mood.points],
        average_mood=mood.average_mood,
        average_wellbeing=mood.average_wellbeing,
        trend=mood.trend,
    )


def require_ai_analysis(user: Authed) -> None:
    """Функция ИИ-анализа доступна не всем тарифам (D9)."""
    if not can_use(user.id, Feature.AI_ANALYSIS):
        raise HTTPException(status_code=403, detail="функция недоступна")


def analysis_router(db: Engine, provider: AiProvider) -> APIRouter:
    router = APIRouter(prefix="/api/analyses")
    gate = [Depends(require_ai_analysis)]

    @router.get("/directions")
    def directions(user: Authed) -> list[DirectionOut]:
        return [DirectionOut(code=d.code, title=d.title) for d in DIRECTIONS]

    @router.get("/mood")
    def mood(start: dt.date, end: dt.date, user: Authed) -> MoodOut:
        try:
            with transaction(db) as session:
                return mood_out(AnalysisService(session, provider).mood(user.id, start, end))
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err

    @router.post("", status_code=201, dependencies=gate)
    def analyze(payload: AnalyzeIn, user: Authed) -> AnalysisOut:
        try:
            with transaction(db) as session:
                outcome = AnalysisService(session, provider).analyze(
                    user.id, payload.direction, payload.start, payload.end, consent=payload.consent
                )
        except ConsentRequiredError as err:
            raise HTTPException(status_code=403, detail=str(err)) from err
        except NoDataError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        except AnalysisFailedError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return outcome_out(outcome)

    @router.post("/{analysis_id}/answers", status_code=201, dependencies=gate)
    def answer(analysis_id: int, payload: AnswersIn, user: Authed) -> AnalysisOut:
        try:
            with transaction(db) as session:
                outcome = AnalysisService(session, provider).answer(
                    user.id, analysis_id, payload.answers, consent=payload.consent
                )
        except ConsentRequiredError as err:
            raise HTTPException(status_code=403, detail=str(err)) from err
        except AnalysisFailedError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        if outcome is None:  # чужой анализ неотличим от несуществующего
            raise HTTPException(status_code=404, detail="анализ не найден")
        return outcome_out(outcome)

    @router.get("")
    def history(user: Authed) -> list[AnalysisOut]:
        with transaction(db) as session:
            return [analysis_out(a) for a in AnalysisService(session, provider).history(user.id)]

    @router.get("/{analysis_id}")
    def get_analysis(analysis_id: int, user: Authed) -> AnalysisOut:
        with transaction(db) as session:
            found = AnalysisService(session, provider).get(user.id, analysis_id)
        if found is None:
            raise HTTPException(status_code=404, detail="анализ не найден")
        return analysis_out(found)

    return router


def create_app(
    engine: Engine | None = None,
    frontend_dist: Path | None = None,
    today: Callable[[], dt.date] = local_today,
    ai_provider: AiProvider | None = None,
) -> FastAPI:
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

    app.include_router(diary_router(db, today))
    app.include_router(day_review_router(db, today))
    app.include_router(progress_router(db, today))
    app.include_router(analysis_router(db, ai_provider or get_provider()))
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
