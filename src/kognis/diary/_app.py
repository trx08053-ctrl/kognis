"""Сценарии дневника. Каждая операция принимает владельца и работает только с его записями."""

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from ._crypto import open_sealed, parse_data_key, seal
from ._domain import (
    DayReview,
    Entry,
    EntryDraft,
    normalize_labels,
    normalize_reflection,
    normalize_text,
    validate_envelope,
    validate_scale,
)
from ._infra import DayReviewRepository, EntryRepository


class DiaryService:
    def __init__(self, session: Session, data_key: str | bytes | None = None) -> None:
        """`data_key` — KOGNIS_DATA_KEY (base64, 32 байта); нужен для записей «под замком»."""
        self._data_key = data_key
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
        return self._add(owner_id, EntryDraft(text, tags, emotions, entry_date), None)

    def create_locked_entry(self, owner_id: int, draft: EntryDraft, password: str) -> Entry:
        """Запись «под замком»: в БД только шифртекст, текст в результате пуст."""
        return self._add(owner_id, draft, password)

    def create_private_entry(
        self,
        owner_id: int,
        envelope: dict[str, Any],
        tags: list[str],
        emotions: list[str],
        entry_date: date | None = None,
    ) -> Entry:
        """Приватная запись: сервер хранит только конверт из браузера (текста у него нет)."""
        entry = Entry(
            0,
            owner_id,
            entry_date or datetime.now(UTC).date(),
            "",
            normalize_labels(tags, "теги"),
            normalize_labels(emotions, "эмоции"),
            envelope=validate_envelope(envelope),
        )
        return self._repo.add(entry)

    def _add(self, owner_id: int, draft: EntryDraft, password: str | None) -> Entry:
        clean = normalize_text(draft.text)
        sealed = seal(self._key(), owner_id, clean, password) if password else None
        entry = Entry(
            0,
            owner_id,
            draft.entry_date or datetime.now(UTC).date(),
            clean,
            normalize_labels(draft.tags, "теги"),
            normalize_labels(draft.emotions, "эмоции"),
        )
        return self._repo.add(entry, sealed)

    def _key(self) -> bytes:
        return parse_data_key(self._data_key)

    def open_entry(self, owner_id: int, entry_id: int, password: str) -> Entry | None:
        """Открыть запись «под замком» на время запроса: текст только в результате, БД не меняется.

        Чужая/несуществующая — `None`; `WrongLockPasswordError` — неверный пароль;
        `EntryUnreadableError` — ключ данных сервера сменился; `DataKeyError` — ключ не задан.
        Обычная запись возвращается как есть.
        """
        entry = self._repo.get(owner_id, entry_id)
        sealed = self._repo.sealed_for(owner_id, entry_id)
        if entry is None or sealed is None:
            return entry
        return replace(entry, text=open_sealed(self._key(), owner_id, sealed, password))

    def lock_entry(self, owner_id: int, entry_id: int, password: str) -> Entry | None:
        """Закрыть обычную запись замком; уже закрытая остаётся как есть."""
        entry = self._repo.get(owner_id, entry_id)
        if entry is None or entry.protection != "plain":
            return entry
        sealed = seal(self._key(), owner_id, entry.text, password)
        self._repo.set_protection(owner_id, entry_id, "", sealed)
        return self._repo.get(owner_id, entry_id)

    def unlock_entry(self, owner_id: int, entry_id: int, password: str) -> Entry | None:
        """Снять замок (нужен пароль): запись снова обычная, текст в открытом виде."""
        opened = self.open_entry(owner_id, entry_id, password)
        if opened is None or opened.protection != "locked":
            return opened
        self._repo.set_protection(owner_id, entry_id, opened.text, None)
        return self._repo.get(owner_id, entry_id)

    def mark_crisis(self, owner_id: int, entry_id: int) -> Entry | None:
        """Пометить запись кризисной (сигнал нашёл safety); чужая или несуществующая — `None`."""
        return self._repo.set_crisis(owner_id, entry_id)

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
