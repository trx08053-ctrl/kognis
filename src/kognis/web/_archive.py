"""Хранитель архива: «В этот день» и мозаика настроения за год (kognis-crn).

Только свои данные, только открытые записи: тексты под замком серверу недоступны,
приватные — шифртекст в браузере; в архив они не попадают (TASK kognis-crn, решение 8).
"""

import datetime as dt
from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import DiaryService
from kognis.users import User

from ._deps import Authed

PROTECTION_PLAIN = "plain"
MONTH_AGO_DAYS = 30  # «В этот день»: запись месяц назад
YEAR_AGO_DAYS = 365  # и год назад
MOOD_YEAR_DAYS = 365  # мозаика настроения: последние 365 дней

AGO_MONTH = "month"  # интерфейс сам подпишет, как давно была запись
AGO_YEAR = "year"


class ArchiveEntryOut(BaseModel):
    id: int
    date: dt.date
    ago: str  # month | year
    text: str
    tags: list[str]
    emotions: list[str]


class OnThisDayOut(BaseModel):
    entries: list[ArchiveEntryOut]


class MoodDayOut(BaseModel):
    date: dt.date
    mood: int  # 1–10 (итог дня)


class MoodYearOut(BaseModel):
    days: list[MoodDayOut]  # дни без итога — пустая клетка, сервер их не отдаёт


def archive_router(db: Engine, today: Callable[[User], dt.date]) -> APIRouter:
    router = APIRouter(prefix="/api/archive")

    @router.get("/on-this-day")
    def on_this_day(user: Authed) -> OnThisDayOut:
        """Свои открытые записи за этот день год и месяц назад."""
        day = today(user)
        with transaction(db) as session:
            service = DiaryService(session)
            found: list[ArchiveEntryOut] = []
            for ago, offset in ((AGO_YEAR, YEAR_AGO_DAYS), (AGO_MONTH, MONTH_AGO_DAYS)):
                target = day - dt.timedelta(days=offset)
                for entry in service.list_entries_between(user.id, target, target):
                    if entry.protection != PROTECTION_PLAIN:
                        continue  # под замком и приватные — не для архива
                    found.append(
                        ArchiveEntryOut(
                            id=entry.id,
                            date=entry.entry_date,
                            ago=ago,
                            text=entry.text,
                            tags=list(entry.tags),
                            emotions=list(entry.emotions),
                        )
                    )
            return OnThisDayOut(entries=found)

    @router.get("/mood-year")
    def mood_year(user: Authed) -> MoodYearOut:
        """Мозаика настроения: итоги дня за последние 365 дней (только свои)."""
        day = today(user)
        with transaction(db) as session:
            start = day - dt.timedelta(days=MOOD_YEAR_DAYS - 1)
            reviews = DiaryService(session).list_day_reviews_between(user.id, start, day)
            return MoodYearOut(days=[MoodDayOut(date=r.review_date, mood=r.mood) for r in reviews])

    return router
