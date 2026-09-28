"""Правила дневника: чистая логика без ввода-вывода."""

from dataclasses import dataclass
from datetime import date

MAX_TEXT_LENGTH = 20_000
MAX_LABELS = 20
MAX_LABEL_LENGTH = 50
MAX_REFLECTION_LENGTH = 5_000
SCALE_MIN = 1
SCALE_MAX = 10


@dataclass(frozen=True)
class Entry:
    id: int
    owner_id: int
    entry_date: date
    text: str
    tags: tuple[str, ...]
    emotions: tuple[str, ...]
    protection: str = "plain"
    crisis: bool = False


@dataclass(frozen=True)
class DayReview:
    id: int
    owner_id: int
    review_date: date
    wellbeing: int
    mood: int
    reflection: str


def validate_scale(value: int, what: str) -> int:
    if not SCALE_MIN <= value <= SCALE_MAX:
        raise ValueError(f"{what}: оценка от {SCALE_MIN} до {SCALE_MAX}")
    return value


def normalize_reflection(raw: str) -> str:
    text = raw.strip()
    if len(text) > MAX_REFLECTION_LENGTH:
        raise ValueError("рефлексия слишком длинная")
    return text


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
