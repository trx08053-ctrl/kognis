"""Хранение пользователей (таблица `users` принадлежит модулю users)."""

from sqlalchemy import Column, Integer, String, Table, insert, select
from sqlalchemy.orm import Session

from kognis.db import metadata

from ._domain import User

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200), nullable=False),
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, name: str) -> User:
        stmt = insert(users_table).values(name=name).returning(users_table.c.id)
        user_id = self._session.execute(stmt).scalar_one()
        return User(id=int(user_id), name=name)

    def get(self, user_id: int) -> User | None:
        row = self._session.execute(select(users_table).where(users_table.c.id == user_id)).first()
        return User(id=row.id, name=row.name) if row else None

    def list_all(self) -> list[User]:
        rows = self._session.execute(select(users_table).order_by(users_table.c.id)).all()
        return [User(id=r.id, name=r.name) for r in rows]
