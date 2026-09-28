"""Правила дневника: чистая логика без ввода-вывода."""

import base64
import binascii
from dataclasses import dataclass
from datetime import date
from typing import Any

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


ENVELOPE_VERSION = 1
ENVELOPE_KDF = "PBKDF2-SHA256"
ENVELOPE_MIN_ITERATIONS = 600_000
ENVELOPE_MAX_ITERATIONS = 10_000_000
ENVELOPE_MIN_SALT = 16
ENVELOPE_IV_SIZE = 12
ENVELOPE_MIN_CIPHER = 16  # AES-GCM: минимум — тег аутентификации
MAX_ENVELOPE_CIPHER = 4 * MAX_TEXT_LENGTH * 2  # base64 шифртекста (UTF-8 до 4 байт на символ)


def _b64_len(value: object, what: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"шифртекст: {what} должно быть строкой base64")
    try:
        return len(base64.b64decode(value, validate=True))
    except (binascii.Error, ValueError) as err:
        raise ValueError(f"шифртекст: {what} — некорректный base64") from err


def validate_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    """Проверить только форму конверта `private`; содержимое сервер прочитать не может."""
    if raw.get("v") != ENVELOPE_VERSION:
        raise ValueError("шифртекст: неизвестная версия формата")
    if raw.get("kdf") != ENVELOPE_KDF:
        raise ValueError("шифртекст: неизвестная функция вывода ключа")
    iterations = raw.get("iter")
    if (
        not isinstance(iterations, int)
        or isinstance(iterations, bool)
        or not ENVELOPE_MIN_ITERATIONS <= iterations <= ENVELOPE_MAX_ITERATIONS
    ):
        raise ValueError("шифртекст: слишком мало итераций вывода ключа")
    salt_size = _b64_len(raw.get("salt"), "соль")
    if salt_size < ENVELOPE_MIN_SALT or _b64_len(raw.get("iv"), "iv") != ENVELOPE_IV_SIZE:
        raise ValueError("шифртекст: некорректные соль или iv")
    cipher = raw.get("ct")
    if _b64_len(cipher, "данные") < ENVELOPE_MIN_CIPHER or len(str(cipher)) > MAX_ENVELOPE_CIPHER:
        raise ValueError("шифртекст: некорректный размер данных")
    return {k: raw[k] for k in ("v", "kdf", "iter", "salt", "iv", "ct")}
