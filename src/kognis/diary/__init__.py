"""Модуль diary: записи дневника (текст, теги, эмоции, дата); владеет `entries`."""

from ._app import DiaryService
from ._domain import Entry

__all__ = ["DiaryService", "Entry"]
