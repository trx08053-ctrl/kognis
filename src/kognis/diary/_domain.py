"""Правила дневника: чистая логика без ввода-вывода."""

import base64
import binascii
from dataclasses import dataclass
from datetime import date
from typing import Any

from kognis.errors import CodedValueError

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100
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
    envelope: dict[str, Any] | None = None  # шифртекст `private` (собран в браузере), непрозрачный


@dataclass(frozen=True)
class EntryDraft:
    """Ввод новой записи до нормализации."""

    text: str
    tags: list[str]
    emotions: list[str]
    entry_date: date | None = None


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
        raise CodedValueError(f"diary.{what}_range", min=SCALE_MIN, max=SCALE_MAX)
    return value


def normalize_reflection(raw: str) -> str:
    text = raw.strip()
    if len(text) > MAX_REFLECTION_LENGTH:
        raise CodedValueError("diary.reflection_long", max=MAX_REFLECTION_LENGTH)
    return text


def normalize_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise CodedValueError("diary.text_empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise CodedValueError("diary.text_long", max=MAX_TEXT_LENGTH)
    return text


def normalize_labels(raw: list[str], what: str) -> tuple[str, ...]:
    """Теги/эмоции: нижний регистр, без пробелов по краям, пустых и повторов; порядок сохранён."""
    seen: dict[str, None] = {}
    for item in raw:
        label = item.strip().lower()
        if not label:
            continue
        if len(label) > MAX_LABEL_LENGTH:
            raise CodedValueError(f"diary.{what}_item_long", max=MAX_LABEL_LENGTH)
        seen[label] = None
    if len(seen) > MAX_LABELS:
        raise CodedValueError(f"diary.{what}_many", max=MAX_LABELS)
    return tuple(seen)


ENVELOPE_VERSION = 1
ENVELOPE_KDF = "PBKDF2-SHA256"
ENVELOPE_MIN_ITERATIONS = 600_000
ENVELOPE_MAX_ITERATIONS = 10_000_000
ENVELOPE_MIN_SALT = 16
ENVELOPE_MAX_SALT = 64
ENVELOPE_IV_SIZE = 12
ENVELOPE_MIN_CIPHER = 16  # AES-GCM: минимум — тег аутентификации
MAX_ENVELOPE_CIPHER = 4 * MAX_TEXT_LENGTH * 2  # base64 шифртекста (UTF-8 до 4 байт на символ)


def _b64_len(value: object) -> int:
    if not isinstance(value, str):
        raise CodedValueError("diary.envelope_invalid")
    try:
        return len(base64.b64decode(value, validate=True))
    except (binascii.Error, ValueError) as err:
        raise CodedValueError("diary.envelope_invalid") from err


def validate_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    """Проверить только форму конверта `private`; содержимое сервер прочитать не может."""
    if raw.get("v") != ENVELOPE_VERSION:
        raise CodedValueError("diary.envelope_invalid")
    if raw.get("kdf") != ENVELOPE_KDF:
        raise CodedValueError("diary.envelope_invalid")
    iterations = raw.get("iter")
    if (
        not isinstance(iterations, int)
        or isinstance(iterations, bool)
        or not ENVELOPE_MIN_ITERATIONS <= iterations <= ENVELOPE_MAX_ITERATIONS
    ):
        raise CodedValueError("diary.envelope_invalid")
    salt_size = _b64_len(raw.get("salt"))
    if (
        not ENVELOPE_MIN_SALT <= salt_size <= ENVELOPE_MAX_SALT
        or _b64_len(raw.get("iv")) != ENVELOPE_IV_SIZE
    ):
        raise CodedValueError("diary.envelope_invalid")
    cipher = raw.get("ct")
    if _b64_len(cipher) < ENVELOPE_MIN_CIPHER or len(str(cipher)) > MAX_ENVELOPE_CIPHER:
        raise CodedValueError("diary.envelope_invalid")
    return {k: raw[k] for k in ("v", "kdf", "iter", "salt", "iv", "ct")}


class InvalidCursorError(CodedValueError):
    """Курсор страницы повреждён или чужого формата."""


def encode_cursor(day: date, entry_id: int | None = None) -> str:
    return day.isoformat() if entry_id is None else f"{day.isoformat()}.{entry_id}"


def decode_cursor(raw: str, *, with_id: bool) -> tuple[date, int]:
    """Курсор `ГГГГ-ММ-ДД[.id]` → (дата, id); у итогов дня id не нужен (дата уникальна)."""
    day_part, _, id_part = raw.partition(".")
    try:
        day = date.fromisoformat(day_part)
        entry_id = int(id_part) if with_id else 0
    except ValueError as err:
        raise InvalidCursorError("diary.cursor_invalid") from err
    if with_id != bool(id_part) or not 0 <= entry_id <= 2**62:
        raise InvalidCursorError("diary.cursor_invalid")
    return day, entry_id


@dataclass(frozen=True)
class EntryFilter:
    """Отбор записей на стороне БД; границы дат включительно."""

    tag: str | None = None
    emotion: str | None = None
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None = None
