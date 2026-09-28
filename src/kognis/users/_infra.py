"""Хранение пользователей и сессий (таблицы `users`, `sessions` принадлежат модулю users)."""

from datetime import UTC, datetime
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    delete,
    false,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import EmailTakenError, User

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("advanced", Boolean, nullable=False, server_default=false()),
)

sessions_table = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("expires_at", DateTime, nullable=False),
)

login_attempts_table = Table(
    "login_attempts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(254), nullable=False, index=True),
    Column("ip", String(64), nullable=False, index=True),
    Column("at", DateTime, nullable=False, index=True),
)

_hasher = PasswordHasher()  # argon2id по умолчанию


def utcnow() -> datetime:
    """Время в UTC без tzinfo — так его хранят и SQLite, и PostgreSQL (TIMESTAMP)."""
    return datetime.now(UTC).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _user(row: Row[Any]) -> User:
    return User(id=row.id, email=row.email, advanced=bool(row.advanced))


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, email: str, password_hash: str) -> User:
        stmt = (
            insert(users_table)
            .values(email=email, password_hash=password_hash, created_at=utcnow())
            .returning(users_table.c.id)
        )
        try:
            with self._session.begin_nested():
                user_id = self._session.execute(stmt).scalar_one()
        except IntegrityError as err:
            raise EmailTakenError("email уже зарегистрирован") from err
        return User(id=int(user_id), email=email)

    def get(self, user_id: int) -> User | None:
        row = self._session.execute(select(users_table).where(users_table.c.id == user_id)).first()
        return _user(row) if row else None

    def set_advanced(self, user_id: int, advanced: bool) -> None:
        self._session.execute(
            update(users_table).where(users_table.c.id == user_id).values(advanced=advanced)
        )

    def find_with_hash(self, email: str) -> tuple[User, str] | None:
        row = self._session.execute(select(users_table).where(users_table.c.email == email)).first()
        return (_user(row), row.password_hash) if row else None


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, token_hash: str, user_id: int, expires_at: datetime) -> None:
        self._session.execute(
            insert(sessions_table).values(
                token_hash=token_hash, user_id=user_id, expires_at=expires_at
            )
        )

    def user_id_for(self, token_hash: str, now: datetime) -> int | None:
        stmt = select(sessions_table.c.user_id).where(
            sessions_table.c.token_hash == token_hash, sessions_table.c.expires_at > now
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def delete(self, token_hash: str) -> None:
        self._session.execute(
            delete(sessions_table).where(sessions_table.c.token_hash == token_hash)
        )


class LoginAttemptRepository:
    """Неудачные попытки входа по email и IP: в БД, поэтому переживают перезапуск."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, email: str, ip: str, at: datetime) -> None:
        self._session.execute(insert(login_attempts_table).values(email=email, ip=ip[:64], at=at))

    def _latest(self, column: Any, value: str, since: datetime, limit: int) -> list[datetime]:
        stmt = (
            select(login_attempts_table.c.at)
            .where(column == value, login_attempts_table.c.at > since)
            .order_by(login_attempts_table.c.at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())

    def latest_by_email(self, email: str, since: datetime, limit: int) -> list[datetime]:
        return self._latest(login_attempts_table.c.email, email, since, limit)

    def latest_by_ip(self, ip: str, since: datetime, limit: int) -> list[datetime]:
        return self._latest(login_attempts_table.c.ip, ip[:64], since, limit)

    def clear_email(self, email: str) -> None:
        self._session.execute(
            delete(login_attempts_table).where(login_attempts_table.c.email == email)
        )

    def purge_before(self, before: datetime) -> None:
        self._session.execute(
            delete(login_attempts_table).where(login_attempts_table.c.at < before)
        )
