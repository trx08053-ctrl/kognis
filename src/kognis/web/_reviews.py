"""Итоги дня."""

import datetime as dt
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from kognis.db import transaction
from kognis.diary import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DayReview,
    DiaryService,
    InvalidCursorError,
)
from kognis.gameplay import (
    GameplayService,
)
from kognis.safety import HelpBlock, check_text
from kognis.users import (
    User,
)

from ._deps import NEXT_CURSOR_HEADER, Authed, HelpOut, Mark, help_out
from ._errors import http_error


class DayReviewIn(BaseModel):
    wellbeing: StrictInt
    mood: StrictInt
    reflection: str = Field(default="", max_length=5_000)
    marks: list[Mark] = Field(default_factory=list, max_length=4)  # отметки рефлексии (XP-бонус)


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
                    GameplayService(session).award_day_review(
                        user.id, review_date, today(user), payload.marks
                    )
                return review

        try:
            try:
                review = save()
            except IntegrityError:
                # два одновременных сохранения за один день: проигравший (уникальность держит БД)
                # повторяет и обновляет уже существующий итог
                review = save()
        except ValueError as err:
            raise http_error(422, err) from err
        return review_out(review, block)

    @router.get("")
    def list_reviews(
        user: Authed,
        response: Response,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
        cursor: Annotated[str | None, Query(max_length=40)] = None,
    ) -> list[DayReviewOut]:
        """Страница итогов, новые первыми; следующая — по курсору из заголовка `X-Next-Cursor`."""
        try:
            with transaction(db) as session:
                page = DiaryService(session).list_day_reviews(user.id, limit=limit, cursor=cursor)
        except InvalidCursorError as err:
            raise http_error(422, err) from err
        if page.next_cursor:
            response.headers[NEXT_CURSOR_HEADER] = page.next_cursor
        return [review_out(r) for r in page.items]

    return router
