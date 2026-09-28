"""Интеграция с PostgreSQL: миграции и сценарии модуля users на настоящей БД."""

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.users import UserService


@pytest.mark.integration
def test_users_on_postgres(pg_engine: Engine) -> None:
    with transaction(pg_engine) as session:
        user = UserService(session).register("Ann")
    with transaction(pg_engine) as session:  # новое соединение: данные сохранились
        assert UserService(session).list_all() == [user]
