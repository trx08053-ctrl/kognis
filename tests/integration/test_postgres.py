"""Интеграция с PostgreSQL: миграции и сценарии users/diary на настоящей БД."""

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import DiaryService
from kognis.users import UserService


@pytest.mark.integration
def test_account_and_entry_on_postgres(pg_engine: Engine) -> None:
    with transaction(pg_engine) as session:
        user = UserService(session).register("ann@example.com", "correct horse")
        entry = DiaryService(session).create_entry(user.id, "текст", ["тег"], ["радость"])
    with transaction(pg_engine) as session:  # новое соединение: данные сохранились
        assert UserService(session).authenticate("ann@example.com", "correct horse") == user
        assert DiaryService(session).list_entries(user.id) == [entry]
