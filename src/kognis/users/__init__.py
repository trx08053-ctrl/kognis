"""Модуль users: регистрация, вход, сессии. Владеет данными пользователей и сессий."""

from ._app import SESSION_LIFETIME, UserService
from ._domain import (
    DEFAULT_LOCALE,
    DEFAULT_TIMEZONE,
    MAX_LOCALE_LENGTH,
    SUPPORTED_LOCALES,
    EmailTakenError,
    InvalidCredentialsError,
    LoginBlockedError,
    User,
    pick_locale,
)

__all__ = [
    "DEFAULT_LOCALE",
    "DEFAULT_TIMEZONE",
    "MAX_LOCALE_LENGTH",
    "SESSION_LIFETIME",
    "SUPPORTED_LOCALES",
    "EmailTakenError",
    "InvalidCredentialsError",
    "LoginBlockedError",
    "User",
    "UserService",
    "pick_locale",
]
