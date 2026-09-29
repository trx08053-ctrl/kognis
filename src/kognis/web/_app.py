"""FastAPI-приложение. Модули вызываются только через публичный API (`users`, `diary`).

Интерфейс — React (frontend/, сборка в frontend/dist); здесь только HTTP API и раздача сборки.
Сессия — cookie `kognis_session` (httpOnly, SameSite=Lax), ADR 0003. Содержимое записей не логируем.
"""

import datetime as dt
import os
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any, Literal
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
from kognis.diary import (
    DataKeyError,
    DayReview,
    DiaryService,
    Entry,
    EntryDraft,
    EntryUnreadableError,
    WrongLockPasswordError,
)
from kognis.gameplay import (
    AlreadyAcceptedError,
    GameplayService,
    Progress,
    Quest,
    QuestService,
    QuizDoneTodayError,
    StepUnavailableError,
)
from kognis.safety import HelpBlock, check_text
from kognis.users import (
    DEFAULT_TIMEZONE,
    SESSION_LIFETIME,
    EmailTakenError,
    InvalidCredentialsError,
    LoginBlockedError,
    User,
    UserService,
)

HERE = Path(__file__).resolve().parent
# сборка фронтенда: <корень проекта>/frontend/dist (в образе — /app/frontend/dist)
DIST = Path(os.environ.get("FRONTEND_DIST", HERE.parents[2] / "frontend" / "dist"))
COOKIE = "kognis_session"
LOCK_ATTEMPTS = 5  # неверных паролей замка на запись за окно, затем 429
LOCK_ATTEMPT_WINDOW = 300.0
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
HSTS = "max-age=31536000; includeSubDomains"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def today_in(timezone: str, now: dt.datetime) -> dt.date:
    """«Сегодня» пользователя: дата в его поясе — единый источник для серий, квестов, периодов."""
    return now.astimezone(ZoneInfo(timezone)).date()


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


class SettingsIn(BaseModel):
    advanced: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)


class EntryIn(BaseModel):
    text: str = ""
    tags: list[str] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    date: dt.date | None = None
    protection: Literal["plain", "locked", "private"] = "plain"
    lock_password: str | None = Field(default=None, max_length=256)
    # `private`: конверт шифртекста, собранный в браузере (текст и пароль на сервер не идут)
    cipher: dict[str, Any] | None = None


class LockPassword(BaseModel):
    password: str = Field(max_length=256)


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
    cipher: dict[str, Any] | None = None
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


def user_out(user: User, today: dt.date) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, advanced=user.advanced, timezone=user.timezone, today=today
    )


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
        cipher=entry.envelope,
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


@contextmanager
def lock_errors() -> Generator[None]:
    """Ошибки записей «под замком» → понятные ответы без раскрытия текста."""
    try:
        yield
    except WrongLockPasswordError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err
    except EntryUnreadableError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    except DataKeyError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err


class AttemptLimiter:
    """Неверные пароли замка по (владелец, запись); в памяти процесса (TD-8)."""

    def __init__(self) -> None:
        self._failures: dict[tuple[int, int], list[float]] = {}

    def _recent(self, key: tuple[int, int]) -> list[float]:
        now = time.monotonic()
        return [t for t in self._failures.get(key, []) if now - t < LOCK_ATTEMPT_WINDOW]

    def check(self, key: tuple[int, int]) -> None:
        if len(self._recent(key)) >= LOCK_ATTEMPTS:
            raise HTTPException(status_code=429, detail="слишком много попыток, попробуйте позже")

    def fail(self, key: tuple[int, int]) -> None:
        self._failures[key] = [*self._recent(key), time.monotonic()]

    def reset(self, key: tuple[int, int]) -> None:
        self._failures.pop(key, None)


def check_protection_fields(payload: EntryIn) -> None:
    """Поля режима защиты согласованы: `private` — только шифртекст, `locked` — с паролем замка."""
    if payload.protection == "private":
        if payload.cipher is None or payload.text or payload.lock_password:
            raise HTTPException(
                status_code=422, detail="приватная запись передаётся только шифртекстом"
            )
    elif payload.cipher is not None:
        raise HTTPException(status_code=422, detail="шифртекст только у приватной записи")
    if payload.protection == "locked" and not payload.lock_password:
        raise HTTPException(status_code=422, detail="для записи «под замком» нужен пароль замка")


def store_entry(diary: DiaryService, owner_id: int, payload: EntryIn, day: dt.date) -> Entry:
    if payload.cipher is not None:
        return diary.create_private_entry(
            owner_id, payload.cipher, payload.tags, payload.emotions, day
        )
    if payload.protection == "locked" and payload.lock_password:
        draft = EntryDraft(payload.text, payload.tags, payload.emotions, day)
        return diary.create_locked_entry(owner_id, draft, payload.lock_password)
    return diary.create_entry(owner_id, payload.text, payload.tags, payload.emotions, day)


def diary_router(db: Engine, today: Callable[[User], dt.date], data_key: str | None) -> APIRouter:
    router = APIRouter(prefix="/api/entries")
    limiter = AttemptLimiter()

    def entry_action(
        user: User, entry_id: int, password: str, action: str, response: Response
    ) -> EntryOut:
        response.headers["Cache-Control"] = "no-store"
        key = (user.id, entry_id)
        limiter.check(key)
        try:
            with lock_errors(), transaction(db) as session:
                entry = getattr(DiaryService(session, data_key), action)(
                    user.id, entry_id, password
                )
        except HTTPException as err:
            if err.status_code == HTTPStatus.FORBIDDEN:
                limiter.fail(key)
            raise
        limiter.reset(key)
        if entry is None:  # чужая запись неотличима от несуществующей
            raise HTTPException(status_code=404, detail="запись не найдена")
        return entry_out(entry)

    @router.post("/{entry_id}/open")
    def open_entry(
        entry_id: int, payload: LockPassword, user: Authed, response: Response
    ) -> EntryOut:
        """Текст записи «под замком» — только в этом ответе, в БД он остаётся зашифрованным."""
        return entry_action(user, entry_id, payload.password, "open_entry", response)

    @router.post("/{entry_id}/lock")
    def lock_entry(
        entry_id: int, payload: LockPassword, user: Authed, response: Response
    ) -> EntryOut:
        try:
            return entry_action(user, entry_id, payload.password, "lock_entry", response)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err

    @router.post("/{entry_id}/unlock")
    def unlock_entry(
        entry_id: int, payload: LockPassword, user: Authed, response: Response
    ) -> EntryOut:
        return entry_action(user, entry_id, payload.password, "unlock_entry", response)

    @router.post("", status_code=201)
    def create_entry(payload: EntryIn, user: Authed) -> EntryOut:
        check_protection_fields(payload)
        try:
            # кризисный сигнал ищем локально (safety); запись сохраняется всегда.
            # У приватной текста на сервере нет — проверяются только теги и эмоции.
            assessment, block = check_text(
                " | ".join([payload.text, *payload.tags, *payload.emotions])
            )
            with lock_errors(), transaction(db) as session:
                diary = DiaryService(session, data_key)
                day = payload.date or today(user)
                entry = store_entry(diary, user.id, payload, day)
                if not assessment.allows_rewards:
                    # кризисная запись опыта не даёт (D5)
                    entry = diary.mark_crisis(user.id, entry.id) or entry
                else:
                    GameplayService(session).award_entry(
                        user.id, entry.id, entry.entry_date, today(user)
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


def day_review_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
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
                    GameplayService(session).award_day_review(user.id, review_date, today(user))
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


def progress_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/progress")

    @router.get("")
    def get_progress(user: Authed) -> ProgressOut:
        with transaction(db) as session:
            return progress_out(GameplayService(session).progress(user.id, today(user)))

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


class QuestStepOut(BaseModel):
    idx: int
    title: str
    done_on: dt.date | None


class QuestOut(BaseModel):
    id: int
    source: str
    template_code: str | None
    kind: str
    title: str
    description: str
    created_on: dt.date
    completed_on: dt.date | None
    steps: list[QuestStepOut]


class StepDoneOut(BaseModel):
    quest: QuestOut
    xp: int


class QuestTemplateOut(BaseModel):
    code: str
    title: str
    description: str
    direction: str
    kind: str
    steps: list[str]


class AcceptIn(BaseModel):
    template: str


class FromAnalysisIn(BaseModel):
    analysis_id: int
    idea: int = Field(ge=0)


def quest_out(quest: Quest) -> QuestOut:
    return QuestOut(
        id=quest.id,
        source=quest.source,
        template_code=quest.template_code,
        kind=quest.kind,
        title=quest.title,
        description=quest.description,
        created_on=quest.created_on,
        completed_on=quest.completed_on,
        steps=[QuestStepOut(idx=s.idx, title=s.title, done_on=s.done_on) for s in quest.steps],
    )


class QuizOut(BaseModel):
    code: str
    title: str
    questions: list[str]
    done_today: bool


class QuizAnswersIn(BaseModel):
    answers: list[str]


class QuizAnswersOut(BaseModel):
    date: dt.date
    answers: list[str]


class QuizResultOut(BaseModel):
    xp: int
    saved: QuizAnswersOut
    help: HelpOut | None = None


def quests_router(db: Engine, today: Callable[[User], dt.date], provider: AiProvider) -> APIRouter:
    router = APIRouter(prefix="/api/quests")

    @router.get("/library")
    def library(user: Authed) -> list[QuestTemplateOut]:
        return [
            QuestTemplateOut(
                code=t.code,
                title=t.title,
                description=t.description,
                direction=t.direction,
                kind="challenge" if t.challenge else "quest",
                steps=list(t.steps),
            )
            for t in QuestService.library()
        ]

    @router.get("")
    def my_quests(user: Authed) -> list[QuestOut]:
        with transaction(db) as session:
            return [quest_out(q) for q in QuestService(session).quests(user.id)]

    @router.post("", status_code=201)
    def accept(payload: AcceptIn, user: Authed) -> QuestOut:
        try:
            with transaction(db) as session:
                quest = QuestService(session).accept_template(
                    user.id, payload.template, today(user)
                )
        except AlreadyAcceptedError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return quest_out(quest)

    @router.post("/from-analysis", status_code=201)
    def from_analysis(payload: FromAnalysisIn, user: Authed) -> QuestOut:
        """Оркестрация (D2): идея берётся из результата анализа, gameplay об анализе не знает."""
        try:
            with transaction(db) as session:
                found = AnalysisService(session, provider).get(user.id, payload.analysis_id)
                if found is None:  # чужой анализ неотличим от несуществующего
                    raise HTTPException(status_code=404, detail="анализ не найден")
                ideas = found.result.quest_ideas if found.result else []
                if payload.idea >= len(ideas):
                    raise HTTPException(status_code=422, detail="нет такой идеи")
                quest = QuestService(session).accept_idea(
                    user.id, found.id, payload.idea, ideas[payload.idea], today(user)
                )
        except AlreadyAcceptedError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return quest_out(quest)

    @router.post("/{quest_id}/steps/{idx}/done")
    def step_done(quest_id: int, idx: int, user: Authed) -> StepDoneOut:
        try:
            with transaction(db) as session:
                outcome = QuestService(session).complete_step(user.id, quest_id, idx, today(user))
        except StepUnavailableError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        if outcome is None:  # чужой квест неотличим от несуществующего
            raise HTTPException(status_code=404, detail="квест не найден")
        return StepDoneOut(quest=quest_out(outcome.quest), xp=outcome.xp)

    return router


def quizzes_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/quizzes")

    @router.get("")
    def quizzes(user: Authed) -> list[QuizOut]:
        with transaction(db) as session:
            statuses = QuestService(session).quiz_statuses(user.id, today(user))
        return [
            QuizOut(
                code=s.quiz.code,
                title=s.quiz.title,
                questions=list(s.quiz.questions),
                done_today=s.done_today,
            )
            for s in statuses
        ]

    @router.post("/{code}/answers", status_code=201)
    def submit(code: str, payload: QuizAnswersIn, user: Authed) -> QuizResultOut:
        # ответы проверяем так же, как записи (D5): кризис — ответы сохраняются, XP нет
        assessment, block = check_text(" | ".join(payload.answers))
        try:
            with transaction(db) as session:
                outcome = QuestService(session).submit_quiz(
                    user.id, code, payload.answers, today(user), reward=assessment.allows_rewards
                )
        except QuizDoneTodayError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        saved = QuizAnswersOut(date=outcome.answers.day, answers=list(outcome.answers.answers))
        return QuizResultOut(xp=outcome.xp, saved=saved, help=help_out(block))

    @router.get("/{code}/answers")
    def history(code: str, user: Authed) -> list[QuizAnswersOut]:
        try:
            with transaction(db) as session:
                items = QuestService(session).quiz_history(user.id, code)
        except ValueError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        return [QuizAnswersOut(date=i.day, answers=list(i.answers)) for i in items]

    return router


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
    app = FastAPI(title="Kognis", dependencies=[Depends(require_json)])
    app.state.db = db

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
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="не найдено")
        page = dist / "index.html"
        if not page.exists():
            return PlainTextResponse(
                "интерфейс не собран: pnpm --dir frontend build", status_code=503
            )
        return FileResponse(page)

    return app


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
