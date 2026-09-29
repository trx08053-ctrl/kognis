"""Отбор записей по метке: SQL для PostgreSQL строится оператором JSONB `@>` (kognis-3mh AC2).

На настоящей БД это проверяет интеграционный тест; здесь — форма запроса без Docker.
"""

from types import SimpleNamespace
from typing import cast

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from kognis.diary._infra import EntryRepository, entries_table


def repository_on(dialect: str) -> EntryRepository:
    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name=dialect))
    )
    return EntryRepository(cast(Session, session))


def test_postgres_uses_jsonb_containment() -> None:
    condition = repository_on("postgresql").has_label(entries_table.c.tags, "работа")
    sql = str(condition.compile(dialect=postgresql.dialect()))
    assert "JSONB" in sql
    assert "@>" in sql


def test_sqlite_uses_json_each() -> None:
    condition = repository_on("sqlite").has_label(entries_table.c.tags, "работа")
    assert "json_each" in str(condition)
