"""Анализ периода и динамика настроения."""

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.access import Feature, can_use
from kognis.ai import AiProvider
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
from kognis.db import transaction
from kognis.safety import HelpBlock

from ._deps import Answer, Authed, HelpOut, help_out
from ._errors import http_error


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
        raise http_error(403, "access.feature_unavailable")


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
            raise http_error(422, err) from err

    @router.post("", status_code=201, dependencies=gate)
    def analyze(payload: AnalyzeIn, user: Authed) -> AnalysisOut:
        try:
            with transaction(db) as session:
                outcome = AnalysisService(session, provider).analyze(
                    user.id, payload.direction, payload.start, payload.end, consent=payload.consent
                )
        except ConsentRequiredError as err:
            raise http_error(403, err) from err
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
    def history(user: Authed) -> list[AnalysisOut]:
        with transaction(db) as session:
            return [analysis_out(a) for a in AnalysisService(session, provider).history(user.id)]

    @router.get("/{analysis_id}")
    def get_analysis(analysis_id: int, user: Authed) -> AnalysisOut:
        with transaction(db) as session:
            found = AnalysisService(session, provider).get(user.id, analysis_id)
        if found is None:
            raise http_error(404, "analysis.not_found")
        return analysis_out(found)

    return router
