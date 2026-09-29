"""Квесты и челленджи."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.ai import AiProvider
from kognis.analysis import (
    AnalysisService,
)
from kognis.db import transaction
from kognis.gameplay import (
    AlreadyAcceptedError,
    Quest,
    QuestService,
    StepUnavailableError,
)
from kognis.users import (
    User,
)

from ._deps import Authed


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
    template: str = Field(max_length=64)


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
