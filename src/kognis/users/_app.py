"""Сценарии users. Изменяет данные пользователей только этот модуль (владелец)."""

from sqlalchemy.orm import Session

from ._domain import User, normalize_name
from ._infra import UserRepository


class UserService:
    def __init__(self, session: Session) -> None:
        self._repo = UserRepository(session)

    def register(self, raw_name: str) -> User:
        return self._repo.add(normalize_name(raw_name))

    def get(self, user_id: int) -> User | None:
        return self._repo.get(user_id)

    def list_all(self) -> list[User]:
        return self._repo.list_all()
