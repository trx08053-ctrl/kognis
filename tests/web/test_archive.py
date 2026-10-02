"""Хранитель архива по HTTP (kognis-crn, AC3): «В этот день» и мозаика — только свои,
записи под замком и приватные в архив не отдаются; IDOR-изоляция пользователей."""

import base64
import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

PW = "correct horse"
LOCK_PW = "замок-дня-архив"
DATA_KEY = base64.b64encode(b"A" * 32).decode()  # ключ записей «под замком» (D4)
TODAY = dt.date(2026, 10, 1)


class Clock:
    def __init__(self, day: dt.date) -> None:
        self.day = day

    def __call__(self) -> dt.datetime:
        return dt.datetime.combine(self.day, dt.time(12), dt.UTC)


@pytest.fixture
def clock() -> Clock:
    return Clock(TODAY)


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    client = TestClient(create_app(engine, clock=clock, data_key=DATA_KEY))
    assert client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": PW}
    ).is_success
    return client


def register_and_login(client: TestClient, email: str) -> None:
    assert client.post("/api/auth/register", json={"email": email, "password": PW}).is_success


def add_entry(
    client: TestClient, day: dt.date, text: str, protection: str = "plain"
) -> dict[str, Any]:
    payload: dict[str, Any] = {"text": text, "date": day.isoformat(), "protection": protection}
    if protection == "locked":
        payload["lock_password"] = LOCK_PW
    r = client.post("/api/entries", json=payload)
    assert r.is_success, r.text
    return r.json()


def review(client: TestClient, clock: Clock, day: dt.date, mood: int) -> None:
    clock.day = day
    r = client.put(f"/api/day-reviews/{day.isoformat()}", json={"wellbeing": 5, "mood": mood})
    assert r.is_success, r.text


@pytest.mark.acceptance("kognis-crn", "AC3")
def test_on_this_day_shows_own_entries_from_year_and_month_ago(
    api: TestClient, clock: Clock
) -> None:
    """Записи за этот день год и месяц назад видны; под замком — нет."""
    year_ago = TODAY - dt.timedelta(days=365)
    month_ago = TODAY - dt.timedelta(days=30)
    add_entry(api, year_ago, "Год назад был хороший день")
    add_entry(api, month_ago, "Месяц назад всё получилось")
    add_entry(api, year_ago, "Под замком", protection="locked")
    add_entry(api, TODAY, "Сегодняшняя запись не попадает в архив этого дня")

    body = api.get("/api/archive/on-this-day").json()
    texts = {e["text"] for e in body["entries"]}
    assert texts == {"Год назад был хороший день", "Месяц назад всё получилось"}
    ago = {e["ago"] for e in body["entries"]}
    assert ago == {"year", "month"}


@pytest.mark.acceptance("kognis-crn", "AC3")
def test_archive_is_isolated_between_users(api: TestClient, clock: Clock) -> None:
    """Чужие записи и итоги в архиве не видны (IDOR): у каждого — только свои."""
    add_entry(api, TODAY - dt.timedelta(days=365), "чужая запись")
    review(api, clock, TODAY, 8)
    other = TestClient(create_app(engine_for(api), clock=clock, data_key=DATA_KEY))
    register_and_login(other, "b@example.com")
    empty = other.get("/api/archive/on-this-day").json()
    assert empty["entries"] == []  # записи пользователя A не видны
    mood = other.get("/api/archive/mood-year").json()
    assert mood["days"] == []  # и его итоги тоже
    own = api.get("/api/archive/mood-year").json()
    assert [d["mood"] for d in own["days"]] == [8]


def test_mood_year_covers_last_365_days(api: TestClient, clock: Clock) -> None:
    """Мозаика отдаёт итоги за год окном 365 дней: старые за пределами окна не отдаются."""
    review(api, clock, TODAY, 9)
    review(api, clock, TODAY - dt.timedelta(days=364), 3)
    review(api, clock, TODAY - dt.timedelta(days=400), 1)  # за пределами окна
    clock.day = TODAY  # окно считается от «сегодня», а часы двигала правка итогов
    days = {d["date"]: d["mood"] for d in api.get("/api/archive/mood-year").json()["days"]}
    assert days == {
        TODAY.isoformat(): 9,
        (TODAY - dt.timedelta(days=364)).isoformat(): 3,
    }


def engine_for(client: TestClient):
    """Engine приложения, на котором создан клиент (общая база для двух пользователей)."""
    return client.app.state.db
