"""Модуль users: регистрация и поиск пользователей. Владеет данными пользователей."""

from ._app import UserService
from ._domain import User

__all__ = ["User", "UserService"]
