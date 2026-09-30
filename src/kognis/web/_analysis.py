"""Анализ периода и динамика настроения."""

import datetime as dt
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.access import Feature, can_use
from kognis.ai import AiProvider
from kognis.analysis import (
    DEFAULT_PAGE_SIZE,
    DIRECTIONS,
    MAX_PAGE_SIZE,
    Analysis,
    AnalysisFailedError,
    AnalysisOutcome,
    AnalysisService,
    ConsentRequiredError,
    DuplicateAnalysisError,
    MoodDynamics,
    NoDataError,
)
from kognis.db import transaction
from kognis.safety import HelpBlock
from kognis.users import User

from ._deps import NEXT_CURSOR_HEADER, Answer, Authed, HelpOut, help_out
from ._errors import http_error

MAX_OFFSET = 1_000_000  # чтобы огромное смещение не превращалось в 500 на int-границе БД


class DirectionOut(BaseModel):
    code: str
    title: str


class AnalyzeIn(BaseModel):
    direction: str = Field(max_length=64)
    start: dt.date
    end: dt.date
    consent: bool = False


class AnswersIn(BaseModel):
    answers: list[Answer] = Field(max_length=10)
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
    changes: list[str]
    answers: list[str]
    created_at: dt.datetime | None
    help: HelpOut | None = None


class PeriodOut(BaseModel):
    start: dt.date
    end: dt.date
    active: bool
    truncated: bool
    last_analysis_id: int | None


class MemoryOut(BaseModel):
    digest: str
    updated_at: dt.datetime | None


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
        changes=result.changes if result else [],
        answers=list(analysis.answers),
        created_at=analysis.created_at.replace(tzinfo=dt.UTC) if analysis.created_at else None,
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
        raise http_error(403, "access.feature_unavailable")


def continuity_routes(
    router: APIRouter, db: Engine, provider: AiProvider, today: Callable[[User], dt.date]
) -> None:
    """Статические маршруты: направления, настроение, период по умолчанию, память ИИ.

    Регистрируются раньше маршрутов с `/{analysis_id}`, чтобы те их не перехватывали."""

    @router.get("/directions")
    def directions(user: Authed) -> list[DirectionOut]:
        return [DirectionOut(code=d.code, title=d.title) for d in DIRECTIONS]

    @router.get("/mood")
    def mood(start: dt.date, end: dt.date, user: Authed) -> MoodOut:
        try:
            with transaction(db) as session:
                return mood_out(AnalysisService(session, provider).mood(user.id, start, end))
        except ValueError as err:
            raise http_error(422, err) from err

    @router.get("/period")
    def period(user: Authed) -> PeriodOut:
        """Период по умолчанию: от конца последнего разбора до сегодня (пояс профиля)."""
        with transaction(db) as session:
            p = AnalysisService(session, provider).default_period(user.id, today(user))
        return PeriodOut(
            start=p.start,
            end=p.end,
            active=p.active,
            truncated=p.truncated,
            last_analysis_id=p.last_analysis_id,
        )

    @router.get("/memory")
    def memory(user: Authed) -> MemoryOut:
        """«Что ИИ помнит обо мне»: только своя память."""
        with transaction(db) as session:
            found = AnalysisService(session, provider).memory(user.id)
        if found is None:
            return MemoryOut(digest="", updated_at=None)
        return MemoryOut(digest=found[0], updated_at=found[1].replace(tzinfo=dt.UTC))

    @router.delete("/memory", status_code=204)
    def clear_memory(user: Authed) -> None:
        with transaction(db) as session:
            AnalysisService(session, provider).clear_memory(user.id)


def analysis_router(
    db: Engine, provider: AiProvider, today: Callable[[User], dt.date]
) -> APIRouter:
    router = APIRouter(prefix="/api/analyses")
    gate = [Depends(require_ai_analysis)]
    continuity_routes(router, db, provider, today)

    @router.post("", status_code=201, dependencies=gate)
    def analyze(payload: AnalyzeIn, user: Authed) -> AnalysisOut:
        try:
            with transaction(db) as session:
                outcome = AnalysisService(session, provider).analyze(
                    user.id, payload.direction, payload.start, payload.end, consent=payload.consent
                )
        except ConsentRequiredError as err:
            raise http_error(403, err) from err
        except DuplicateAnalysisError as err:
            raise http_error(409, err) from err
        except NoDataError as err:
            raise http_error(422, err) from err
        except AnalysisFailedError as err:
            raise http_error(502, err) from err
        except ValueError as err:
            raise http_error(422, err) from err
        return outcome_out(outcome)

    @router.post("/{analysis_id}/answers", status_code=201, dependencies=gate)
    def answer(analysis_id: int, payload: AnswersIn, user: Authed) -> AnalysisOut:
        try:
            with transaction(db) as session:
                outcome = AnalysisService(session, provider).answer(
                    user.id, analysis_id, payload.answers, consent=payload.consent
                )
        except ConsentRequiredError as err:
            raise http_error(403, err) from err
        except AnalysisFailedError as err:
            raise http_error(502, err) from err
        except ValueError as err:
            raise http_error(422, err) from err
        if outcome is None:  # чужой анализ неотличим от несуществующего
            raise http_error(404, "analysis.not_found")
        return outcome_out(outcome)

    @router.get("")
    def history(
        user: Authed,
        response: Response,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
        offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
    ) -> list[AnalysisOut]:
        """Страница истории, новые первыми; смещение следующей — в заголовке `X-Next-Cursor`."""
        with transaction(db) as session:
            page = AnalysisService(session, provider).history(user.id, limit=limit, offset=offset)
        if page.next_offset is not None:
            response.headers[NEXT_CURSOR_HEADER] = str(page.next_offset)
        return [analysis_out(a) for a in page.items]

    @router.delete("/{analysis_id}", status_code=204)
    def delete_analysis(analysis_id: int, user: Authed) -> None:
        with transaction(db) as session:
            deleted = AnalysisService(session, provider).delete(user.id, analysis_id)
        if not deleted:  # чужой анализ неотличим от несуществующего
            raise http_error(404, "analysis.not_found")

    @router.get("/{analysis_id}")
    def get_analysis(analysis_id: int, user: Authed) -> AnalysisOut:
        with transaction(db) as session:
            found = AnalysisService(session, provider).get(user.id, analysis_id)
        if found is None:
            raise http_error(404, "analysis.not_found")
        return analysis_out(found)

    return router
