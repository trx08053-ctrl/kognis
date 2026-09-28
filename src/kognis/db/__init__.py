"""Платформа данных: подключение, метаданные таблиц, транзакции.

Таблицы объявляют модули-владельцы (`<модуль>/_infra.py`) на общем `metadata`; схему меняют
только миграции Alembic (`migrations/`). URL — DATABASE_URL (по умолчанию локальный SQLite).
"""

import os
from contextlib import AbstractContextManager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

metadata = MetaData()


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./local.db")


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())


def transaction(engine: Engine) -> AbstractContextManager[Session]:
    """Сессия с коммитом при успехе и откатом при ошибке: `with transaction(engine) as session:`."""
    return sessionmaker(engine).begin()


__all__ = ["database_url", "make_engine", "metadata", "transaction"]
