"""Сценарии users. Изменяет данные пользователей и сессий только этот модуль (владелец)."""

import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from ._domain import (
    InvalidCredentialsError,
    User,
    hash_token,
    normalize_email,
    validate_password,
)
from ._infra import (
    SessionRepository,
    UserRepository,
    hash_password,
    utcnow,
    verify_password,
)

SESSION_LIFETIME = timedelta(days=30)


class UserService:
    def __init__(self, session: Session) -> None:
        self._users = UserRepository(session)
        self._sessions = SessionRepository(session)

    def register(self, raw_email: str, password: str) -> User:
        email = normalize_email(raw_email)
        validate_password(password)
        return self._users.add(email, hash_password(password))

    def authenticate(self, raw_email: str, password: str) -> User:
        try:
            email = normalize_email(raw_email)
        except ValueError as err:
            raise InvalidCredentialsError("неверный email или пароль") from err
        found = self._users.find_with_hash(email)
        if found is None:
            # выравниваем время ответа, чтобы не раскрывать существование email
            verify_password(hash_password("dummy-password"), password)
            raise InvalidCredentialsError("неверный email или пароль")
        user, password_hash = found
        if not verify_password(password_hash, password):
            raise InvalidCredentialsError("неверный email или пароль")
        return user

    def start_session(self, user_id: int) -> str:
        """Новая сессия; возвращает токен для cookie (в БД лежит только его хэш)."""
        token = secrets.token_urlsafe(32)
        self._sessions.add(hash_token(token), user_id, utcnow() + SESSION_LIFETIME)
        return token

    def user_for_token(self, token: str) -> User | None:
        user_id = self._sessions.user_id_for(hash_token(token), utcnow())
        return self._users.get(user_id) if user_id is not None else None

    def end_session(self, token: str) -> None:
        self._sessions.delete(hash_token(token))
