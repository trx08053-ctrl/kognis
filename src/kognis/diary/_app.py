"""Сценарии дневника. Каждая операция принимает владельца и работает только с его записями."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from ._domain import (
    DayReview,
    Entry,
    normalize_labels,
    normalize_reflection,
    normalize_text,
    validate_scale,
)
from ._infra import DayReviewRepository, EntryRepository


class DiaryService:
    def __init__(self, session: Session) -> None:
        self._repo = EntryRepository(session)
        self._reviews = DayReviewRepository(session)

    def create_entry(
        self,
        owner_id: int,
        text: str,
        tags: list[str],
        emotions: list[str],
        entry_date: date | None = None,
    ) -> Entry:
        return self._repo.add(
            owner_id,
            entry_date or datetime.now(UTC).date(),
            normalize_text(text),
            normalize_labels(tags, "теги"),
            normalize_labels(emotions, "эмоции"),
        )

    def get_entry(self, owner_id: int, entry_id: int) -> Entry | None:
        """Чужая или несуществующая запись неотличимы: `None`."""
        return self._repo.get(owner_id, entry_id)

    def list_entries(self, owner_id: int) -> list[Entry]:
        return self._repo.list_for(owner_id)

    def save_day_review(
        self, owner_id: int, review_date: date, wellbeing: int, mood: int, reflection: str
    ) -> DayReview:
        """Один итог на день: повторное сохранение за ту же дату исправляет существующий."""
        return self._reviews.upsert(
            owner_id,
            review_date,
            validate_scale(wellbeing, "самочувствие"),
            validate_scale(mood, "настроение"),
            normalize_reflection(reflection),
        )

    def list_day_reviews(self, owner_id: int) -> list[DayReview]:
        return self._reviews.list_for(owner_id)
