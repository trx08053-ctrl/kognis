"""Интеграция с PostgreSQL: миграции и сценарии users/diary на настоящей БД."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import DiaryService, EntryFilter
from kognis.users import UserService


@pytest.mark.integration
def test_account_and_entry_on_postgres(pg_engine: Engine) -> None:
    with transaction(pg_engine) as session:
        user = UserService(session).register("ann@example.com", "correct horse")
        entry = DiaryService(session).create_entry(user.id, "текст", ["тег"], ["радость"])
    with transaction(pg_engine) as session:  # новое соединение: данные сохранились
        assert UserService(session).authenticate("ann@example.com", "correct horse") == user
        assert DiaryService(session).list_entries(user.id).items == [entry]


@pytest.mark.integration
def test_paging_and_label_filters_on_postgres(pg_engine: Engine) -> None:
    """Курсор и отбор по JSON-меткам (`jsonb @>`) на настоящей БД (kognis-3mh)."""
    with transaction(pg_engine) as session:
        user = UserService(session).register("ann@example.com", "correct horse")
        service = DiaryService(session)
        for n in range(5):
            day = date(2026, 8, 1 + n)
            service.create_entry(user.id, f"запись {n}", ["работа" if n % 2 else "дом"], [], day)
    with transaction(pg_engine) as session:
        service = DiaryService(session)
        where = EntryFilter(tag="дом")
        first = service.list_entries(user.id, limit=2, where=where)
        assert [e.text for e in first.items] == ["запись 4", "запись 2"]
        rest = service.list_entries(user.id, limit=2, cursor=first.next_cursor, where=where)
        assert [e.text for e in rest.items] == ["запись 0"]
        assert rest.next_cursor is None
