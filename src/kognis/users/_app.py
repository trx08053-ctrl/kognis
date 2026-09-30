"""Сценарии users. Изменяет данные пользователей и сессий только этот модуль (владелец)."""

import math
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ._domain import (
    DEFAULT_LOCALE,
    DEFAULT_TIMEZONE,
    LOGIN_MAX_FAILURES_PER_EMAIL,
    LOGIN_MAX_FAILURES_PER_IP,
    LOGIN_WINDOW,
    InvalidCredentialsError,
    LoginBlockedError,
    User,
    attempt_key,
    hash_token,
    normalize_email,
    validate_locale,
    validate_password,
    validate_timezone,
)
from ._infra import (
    LoginAttemptRepository,
    SessionRepository,
    UserRepository,
    hash_password,
    utcnow,
    verify_password,
)

SESSION_LIFETIME = timedelta(days=30)
_DUMMY_HASH = hash_password("dummy-password")  # одна проверка argon2, как и для известного email


class UserService:
    def __init__(self, session: Session) -> None:
        self._users = UserRepository(session)
        self._sessions = SessionRepository(session)
        self._attempts = LoginAttemptRepository(session)

    def register(
        self,
        raw_email: str,
        password: str,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> User:
        email = normalize_email(raw_email)
        validate_password(password)
        zone = validate_timezone(timezone) if timezone is not None else DEFAULT_TIMEZONE
        language = validate_locale(locale) if locale is not None else DEFAULT_LOCALE
        return self._users.add(email, hash_password(password), zone, language)

    def authenticate(self, raw_email: str, password: str) -> User:
        try:
            email = normalize_email(raw_email)
        except ValueError as err:
            raise InvalidCredentialsError("user.credentials_invalid") from err
        found = self._users.find_with_hash(email)
        if found is None:
            # выравниваем время ответа, чтобы не раскрывать существование email
            verify_password(_DUMMY_HASH, password)
            raise InvalidCredentialsError("user.credentials_invalid")
        user, password_hash = found
        if not verify_password(password_hash, password):
            raise InvalidCredentialsError("user.credentials_invalid")
        return user

    def ensure_login_allowed(self, raw_email: str, ip: str, now: datetime | None = None) -> None:
        """Бросает LoginBlockedError, если с этого email или IP слишком много неудач за окно."""
        now = now or utcnow()
        since = now - LOGIN_WINDOW
        email = attempt_key(raw_email)
        by_email = self._attempts.latest_by_email(email, since, LOGIN_MAX_FAILURES_PER_EMAIL)
        by_ip = self._attempts.latest_by_ip(ip, since, LOGIN_MAX_FAILURES_PER_IP)
        # блок снимется, когда самая давняя из последних неудач выйдет из окна
        unblock = [
            recent[-1] + LOGIN_WINDOW
            for recent, limit in (
                (by_email, LOGIN_MAX_FAILURES_PER_EMAIL),
                (by_ip, LOGIN_MAX_FAILURES_PER_IP),
            )
            if len(recent) >= limit
        ]
        if unblock:
            raise LoginBlockedError(max(1, math.ceil((max(unblock) - now).total_seconds())))

    def record_login_failure(self, raw_email: str, ip: str, now: datetime | None = None) -> None:
        now = now or utcnow()
        self._attempts.purge_before(now - LOGIN_WINDOW)
        self._attempts.add(attempt_key(raw_email), ip, now)

    def clear_login_failures(self, raw_email: str) -> None:
        """Успешный вход сбрасывает счётчик email (счётчик IP остаётся: он про перебор с адреса)."""
        self._attempts.clear_email(attempt_key(raw_email))

    def set_advanced(self, user_id: int, advanced: bool) -> None:
        """Сохранить режим интерфейса в профиле."""
        self._users.set_advanced(user_id, advanced)

    def set_timezone(self, user_id: int, timezone: str) -> None:
        """Сохранить часовой пояс профиля (IANA); неизвестный — ValueError."""
        self._users.set_timezone(user_id, validate_timezone(timezone))

    def set_locale(self, user_id: int, locale: str) -> None:
        """Сохранить язык профиля; неподдерживаемый код — CodedValueError."""
        self._users.set_locale(user_id, validate_locale(locale))

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
