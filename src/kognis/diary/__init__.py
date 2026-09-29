"""Модуль diary: записи дневника и итоги дня; владеет `entries` и `day_reviews`."""

from ._app import DiaryService
from ._crypto import (
    MIN_LOCK_PASSWORD,
    DataKeyError,
    EntryUnreadableError,
    WrongLockPasswordError,
)
from ._domain import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DayReview,
    Entry,
    EntryDraft,
    EntryFilter,
    InvalidCursorError,
    Page,
)

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MIN_LOCK_PASSWORD",
    "DataKeyError",
    "DayReview",
    "DiaryService",
    "Entry",
    "EntryDraft",
    "EntryFilter",
    "EntryUnreadableError",
    "InvalidCursorError",
    "Page",
    "WrongLockPasswordError",
]
