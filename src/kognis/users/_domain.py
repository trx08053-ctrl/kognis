"""Правила пользователей: чистая логика без ввода-вывода."""

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_EMAIL_LENGTH = 254
MAX_TIMEZONE_LENGTH = 64
DEFAULT_TIMEZONE = "Europe/Moscow"  # пояс по умолчанию (D11), пока пользователь не задал свой
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256
LOGIN_WINDOW = timedelta(minutes=15)  # окно подсчёта неудачных попыток входа
LOGIN_MAX_FAILURES_PER_EMAIL = 5
LOGIN_MAX_FAILURES_PER_IP = 20  # выше, чем на email: за одним IP (NAT) могут сидеть многие


@dataclass(frozen=True)
class User:
    id: int
    email: str
    advanced: bool = False  # режим интерфейса: простой (по умолчанию) или Advanced
    timezone: str = DEFAULT_TIMEZONE  # IANA; по нему считается «сегодня» пользователя


class EmailTakenError(ValueError):
    """Пользователь с таким email уже есть."""


class InvalidCredentialsError(ValueError):
    """Неверный email или пароль (причину намеренно не раскрываем)."""


class LoginBlockedError(Exception):
    """Слишком много неудачных попыток входа; вход заблокирован на `retry_after` секунд."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("слишком много попыток входа, попробуйте позже")
        self.retry_after = retry_after


def normalize_email(raw: str) -> str:
    """email в нижнем регистре без пробелов по краям; минимальная проверка формата."""
    email = raw.strip().lower()
    local, at, domain = email.partition("@")
    if not at or not local or "." not in domain or " " in email or len(email) > MAX_EMAIL_LENGTH:
        raise ValueError("некорректный email")
    return email


def attempt_key(raw_email: str) -> str:
    """Ключ учёта попыток: нормализованный email, а для мусорного ввода — его усечённая копия."""
    try:
        return normalize_email(raw_email)
    except ValueError:
        return raw_email.strip().lower()[:MAX_EMAIL_LENGTH]


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("пароль слишком длинный")


def validate_timezone(name: str) -> str:
    """Имя пояса IANA (например, Asia/Vladivostok); неизвестное отклоняется."""
    try:
        if not name or name != name.strip() or len(name) > MAX_TIMEZONE_LENGTH:
            raise ValueError(name)
        ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError, OSError) as err:
        raise ValueError("неизвестный часовой пояс") from err
    return name


def hash_token(token: str) -> str:
    """В БД хранится только SHA-256 токена сессии, сам токен — только в cookie пользователя."""
    return hashlib.sha256(token.encode()).hexdigest()
