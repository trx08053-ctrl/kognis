"""Правила дневника: чистая логика без ввода-вывода."""

from dataclasses import dataclass
from datetime import date

MAX_TEXT_LENGTH = 20_000
MAX_LABELS = 20
MAX_LABEL_LENGTH = 50


@dataclass(frozen=True)
class Entry:
    id: int
    owner_id: int
    entry_date: date
    text: str
    tags: tuple[str, ...]
    emotions: tuple[str, ...]
    protection: str = "plain"


def normalize_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise ValueError("текст записи не может быть пустым")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError("запись слишком длинная")
    return text


def normalize_labels(raw: list[str], what: str) -> tuple[str, ...]:
    """Теги/эмоции: нижний регистр, без пробелов по краям, пустых и повторов; порядок сохранён."""
    seen: dict[str, None] = {}
    for item in raw:
        label = item.strip().lower()
        if not label:
            continue
        if len(label) > MAX_LABEL_LENGTH:
            raise ValueError(f"{what}: слишком длинное значение")
        seen[label] = None
    if len(seen) > MAX_LABELS:
        raise ValueError(f"{what}: не больше {MAX_LABELS}")
    return tuple(seen)
