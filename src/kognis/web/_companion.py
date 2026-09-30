"""Цифровые герои: спутник и наставники."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import CompanionState, HeroService
from kognis.users import User

from ._deps import Authed
from ._errors import http_error


class LineOut(BaseModel):
    hero: str
    situation: str


class PostcardOut(BaseModel):
    code: str
    for_day: dt.date


class MentorOut(BaseModel):
    code: str
    direction: str
    unlocked: bool


class CompanionOut(BaseModel):
    chosen: bool
    appearance: str | None
    name: str | None
    address: str | None
    stage: int
    days_total: int
    days_to_next: int | None
    resting: bool
    line: LineOut | None
    postcard: PostcardOut | None
    mentors: list[MentorOut]


class CompanionIn(BaseModel):
    appearance: str = Field(max_length=16)
    name: str = Field(max_length=64)
    address: str = Field(max_length=2)


def companion_out(state: CompanionState) -> CompanionOut:
    line, card = state.line, state.postcard
    return CompanionOut(
        chosen=state.chosen,
        appearance=state.appearance,
        name=state.name,
        address=state.address,
        stage=state.stage,
        days_total=state.days_total,
        days_to_next=state.days_to_next,
        resting=state.resting,
        line=LineOut(hero=line.hero, situation=line.situation) if line else None,
        postcard=PostcardOut(code=card.code, for_day=card.for_day) if card else None,
        mentors=[
            MentorOut(code=m.code, direction=m.direction, unlocked=m.unlocked)
            for m in state.mentors
        ],
    )


def companion_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/companion")

    @router.get("")
    def get_companion(user: Authed) -> CompanionOut:
        with transaction(db) as session:
            return companion_out(HeroService(session).state(user.id, today(user)))

    @router.put("")
    def put_companion(payload: CompanionIn, user: Authed) -> CompanionOut:
        """Облик, имя и обращение (ты/вы): знакомство со спутником или смена выбора."""
        try:
            with transaction(db) as session:
                state = HeroService(session).choose(
                    user.id, payload.appearance, payload.name, payload.address, today(user)
                )
        except ValueError as err:
            raise http_error(422, err) from err
        return companion_out(state)

    @router.post("/seen")
    def post_seen(user: Authed) -> CompanionOut:
        """Реплика о новой стадии показана — повторно не предлагать."""
        with transaction(db) as session:
            return companion_out(HeroService(session).mark_stage_seen(user.id, today(user)))

    return router
