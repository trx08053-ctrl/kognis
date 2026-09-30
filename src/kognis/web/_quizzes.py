"""Опросники."""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import (
    QuestService,
    QuizDoneTodayError,
)
from kognis.safety import check_text
from kognis.users import (
    User,
)

from ._deps import Answer, Authed, HelpOut, help_out
from ._errors import http_error


class QuizOut(BaseModel):
    code: str
    title: str
    questions: list[str]
    done_today: bool


class QuizAnswersIn(BaseModel):
    answers: list[Answer] = Field(max_length=20)


class QuizAnswersOut(BaseModel):
    date: dt.date
    answers: list[str]


class QuizResultOut(BaseModel):
    xp: int
    saved: QuizAnswersOut
    help: HelpOut | None = None


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
            raise http_error(409, err) from err
        except ValueError as err:
            raise http_error(422, err) from err
        saved = QuizAnswersOut(date=outcome.answers.day, answers=list(outcome.answers.answers))
        return QuizResultOut(xp=outcome.xp, saved=saved, help=help_out(block))

    @router.get("/{code}/answers")
    def history(code: str, user: Authed) -> list[QuizAnswersOut]:
        try:
            with transaction(db) as session:
                items = QuestService(session).quiz_history(user.id, code)
        except ValueError as err:
            raise http_error(404, err) from err
        return [QuizAnswersOut(date=i.day, answers=list(i.answers)) for i in items]

    return router
