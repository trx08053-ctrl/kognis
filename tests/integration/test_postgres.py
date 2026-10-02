"""Интеграция с PostgreSQL: миграции и сценарии users/diary на настоящей БД."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.diary import DiaryService, EntryFilter
from kognis.gameplay import NotEnoughSparksError, OwnedItemError, SparkRepository, item_by_code
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


@pytest.mark.integration
def test_spark_purchase_on_postgres(pg_engine: Engine) -> None:
    """Покупка искр на настоящей БД: advisory-лок, баланс, идемпотентность (kognis-crn)."""
    scarf = item_by_code("scarf")
    with transaction(pg_engine) as session:
        repo = SparkRepository(session)
        repo.add_spark_once(1, "weekly_goal", "2026-W37", date(2026, 9, 7), 60)
        with pytest.raises(NotEnoughSparksError):
            repo.add_purchase(1, "bg_forest", "once", 75, date(2026, 9, 7))
        repo.add_purchase(1, scarf.code, "once", scarf.price, date(2026, 9, 7))
        assert repo.balance(1) == 10
        with pytest.raises(OwnedItemError):
            repo.add_purchase(1, scarf.code, "once", scarf.price, date(2026, 9, 8))
        assert repo.balance(1) == 10
