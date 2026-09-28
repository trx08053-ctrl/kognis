"""Модуль diary: записи дневника и итоги дня; владеет `entries` и `day_reviews`."""

from ._app import DiaryService
from ._domain import DayReview, Entry

__all__ = ["DayReview", "DiaryService", "Entry"]
