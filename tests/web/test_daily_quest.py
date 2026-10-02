"""Квест дня по HTTP (kognis-crn, AC2): выбор 1 из 3, один раз в день, штрафа за пропуск нет."""

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

PW = "correct horse"
MON = dt.date(2026, 9, 7)  # понедельник


class Clock:
    def __init__(self, day: dt.date) -> None:
        self.day = day

    def __call__(self) -> dt.datetime:
        return dt.datetime.combine(self.day, dt.time(12), dt.UTC)


@pytest.fixture
def clock() -> Clock:
    return Clock(MON)


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    client = TestClient(create_app(engine, clock=clock))
    assert client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": PW}
    ).is_success
    return client


def daily(client: TestClient) -> dict[str, Any]:
    return client.get("/api/daily-quest").json()


def choose(client: TestClient, code: str) -> Any:
    return client.post("/api/daily-quest/choose", json={"code": code})


@pytest.mark.acceptance("kognis-crn", "AC2")
def test_three_options_one_choice_per_day(api: TestClient, clock: Clock) -> None:
    """Три варианта; выбор фиксируется один раз в день — повтор в тот же день 409."""
    body = daily(api)
    assert len(body["options"]) == 3
    assert body["picked"] is None
    assert body["done"] is False
    ok = choose(api, body["options"][0])
    assert ok.status_code == 200, ok.text
    assert ok.json()["picked"] == body["options"][0]
    second = choose(api, body["options"][1])  # сменить в тот же день нельзя
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "gameplay.daily_picked"
    assert daily(api)["picked"] == body["options"][0]


def test_completion_marks_done_once_and_next_day_is_fresh(api: TestClient, clock: Clock) -> None:
    """Выполнение отмечается один раз; на следующий день — новые варианты без штрафа."""
    first = daily(api)
    choose(api, first["options"][2])
    done = api.post("/api/daily-quest/done", json={})
    assert done.status_code == 200
    assert done.json()["done"] is True
    again = api.post("/api/daily-quest/done", json={})  # повторная отметка — ничего не меняет
    assert again.status_code == 200
    assert again.json()["done"] is True

    clock.day = MON + dt.timedelta(days=1)  # пропуск был или нет — новый день чистый
    fresh = daily(api)
    assert fresh["picked"] is None
    assert fresh["done"] is False
    assert len(fresh["options"]) == 3


def test_choice_must_be_from_todays_options(api: TestClient) -> None:
    r = choose(api, "no_such_code")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "gameplay.daily_unknown"


def test_done_without_choice_is_422(api: TestClient) -> None:
    r = api.post("/api/daily-quest/done", json={})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "gameplay.daily_not_picked"


def test_completion_gives_xp_and_sparks_once(api: TestClient, clock: Clock) -> None:
    """Выполнение дня: +10 XP и +5 искров за день, повтор — без начислений."""
    first = daily(api)
    choose(api, first["options"][0])
    api.post("/api/daily-quest/done", json={})
    progress = client_progress(api)
    sparks = client_sparks(api)
    assert progress["xp"] == 10
    assert sparks["balance"] == 5  # только задание дня
    api.post("/api/daily-quest/done", json={})  # повтор
    assert client_progress(api)["xp"] == 10
    assert client_sparks(api)["balance"] == 5


def client_progress(client: TestClient) -> dict[str, Any]:
    return client.get("/api/progress").json()


def client_sparks(client: TestClient) -> dict[str, Any]:
    return client.get("/api/sparks").json()
