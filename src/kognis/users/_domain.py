"""Правила пользователей: чистая логика без ввода-вывода."""

import hashlib
from dataclasses import dataclass

MAX_EMAIL_LENGTH = 254
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256


@dataclass(frozen=True)
class User:
    id: int
    email: str
    advanced: bool = False  # режим интерфейса: простой (по умолчанию) или Advanced


class EmailTakenError(ValueError):
    """Пользователь с таким email уже есть."""


class InvalidCredentialsError(ValueError):
    """Неверный email или пароль (причину намеренно не раскрываем)."""


def normalize_email(raw: str) -> str:
    """email в нижнем регистре без пробелов по краям; минимальная проверка формата."""
    email = raw.strip().lower()
    local, at, domain = email.partition("@")
    if not at or not local or "." not in domain or " " in email or len(email) > MAX_EMAIL_LENGTH:
        raise ValueError("некорректный email")
    return email


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("пароль слишком длинный")


def hash_token(token: str) -> str:
    """В БД хранится только SHA-256 токена сессии, сам токен — только в cookie пользователя."""
    return hashlib.sha256(token.encode()).hexdigest()
