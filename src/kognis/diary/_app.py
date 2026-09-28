"""Сценарии дневника. Каждая операция принимает владельца и работает только с его записями."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from ._domain import Entry, normalize_labels, normalize_text
from ._infra import EntryRepository


class DiaryService:
    def __init__(self, session: Session) -> None:
        self._repo = EntryRepository(session)

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
