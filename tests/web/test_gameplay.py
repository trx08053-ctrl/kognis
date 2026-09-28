"""Игровое ядро по HTTP: приёмочные тесты kognis-50k (AC1–AC3)."""

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

VALID_PW = "correct horse"


class Clock:
    """Управляемое «сегодня» пользователя."""

    def __init__(self, day: dt.date) -> None:
        self.day = day

    def __call__(self) -> dt.date:
        return self.day


@pytest.fixture
def clock() -> Clock:
    return Clock(dt.date(2026, 9, 1))


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    return TestClient(create_app(engine, today=clock))


def signup(client: TestClient, email: str = "ann@example.com") -> None:
    response = client.post("/api/auth/register", json={"email": email, "password": VALID_PW})
    assert response.status_code == 201


def write(client: TestClient, day: str, text: str = "Хороший день") -> None:
    response = client.post("/api/entries", json={"text": text, "date": day})
    assert response.status_code == 201


def progress(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/progress")
    assert response.status_code == 200
    return response.json()


def review(client: TestClient, day: str) -> None:
    response = client.put(f"/api/day-reviews/{day}", json={"wellbeing": 5, "mood": 5})
    assert response.status_code == 200


def test_progress_requires_login(api: TestClient) -> None:
    assert api.get("/api/progress").status_code == 401


def test_new_user_starts_at_level_one(api: TestClient) -> None:
    signup(api)
    assert progress(api) == {
        "xp": 0,
        "level": 1,
        "level_start_xp": 0,
        "next_level_xp": 50,
        "streak": 0,
        "achievements": [],
    }


@pytest.mark.acceptance("kognis-50k", "AC1")
def test_entry_xp_capped_at_three_per_day_review_adds_twenty(api: TestClient) -> None:
    signup(api)
    write(api, "2026-09-01")
    assert progress(api)["xp"] == 10
    for _ in range(4):  # всего пять записей за день
        write(api, "2026-09-01")
    assert progress(api)["xp"] == 30  # только первые три

    write(api, "2026-08-31")  # другой день — свой лимит
    assert progress(api)["xp"] == 40

    review(api, "2026-09-01")
    assert progress(api)["xp"] == 60
    review(api, "2026-09-01")  # повторное сохранение того же итога XP не даёт
    assert progress(api)["xp"] == 60


@pytest.mark.acceptance("kognis-50k", "AC1")
def test_level_grows_by_table(api: TestClient) -> None:
    signup(api)
    for day in range(1, 3):  # 2 дня по 3 записи = 60 XP → уровень 2 (порог 50)
        for _ in range(3):
            write(api, f"2026-08-{day:02d}")
    state = progress(api)
    assert (state["xp"], state["level"]) == (60, 2)
    assert (state["level_start_xp"], state["next_level_xp"]) == (50, 120)


@pytest.mark.acceptance("kognis-50k", "AC1")
def test_crisis_entry_gives_no_xp(api: TestClient) -> None:
    signup(api)
    response = api.post("/api/entries", json={"text": "не хочу жить", "date": "2026-09-01"})
    assert response.json()["crisis"] is True
    state = progress(api)
    assert (state["xp"], state["streak"], state["achievements"]) == (0, 0, [])


@pytest.mark.acceptance("kognis-50k", "AC2")
def test_streak_counts_consecutive_days_and_resets_on_gap(api: TestClient, clock: Clock) -> None:
    signup(api)
    write(api, "2026-09-01")
    review(api, "2026-09-02")  # итог дня тоже держит серию
    clock.day = dt.date(2026, 9, 2)
    assert progress(api)["streak"] == 2

    clock.day = dt.date(2026, 9, 3)  # вчера активность была — серия жива
    assert progress(api)["streak"] == 2

    clock.day = dt.date(2026, 9, 6)  # пропуск больше одного дня — сброс
    assert progress(api)["streak"] == 0


@pytest.mark.acceptance("kognis-50k", "AC2")
def test_one_freeze_per_week_bridges_single_missed_day(api: TestClient, clock: Clock) -> None:
    signup(api)
    # 2026-09-07 — понедельник. Пн, вт, (ср пропуск), чт: заморозка недели гасит пропуск
    for day in ("2026-09-07", "2026-09-08", "2026-09-10"):
        write(api, day)
    clock.day = dt.date(2026, 9, 10)
    assert progress(api)["streak"] == 3

    write(api, "2026-09-12")  # пт пропущен: вторая заморозка в той же неделе невозможна
    clock.day = dt.date(2026, 9, 12)
    assert progress(api)["streak"] == 1

    # в новой неделе заморозка снова есть: пн 14, (вт пропуск), ср 16
    for day in ("2026-09-14", "2026-09-16"):
        write(api, day)
    clock.day = dt.date(2026, 9, 16)
    assert progress(api)["streak"] == 2


@pytest.mark.acceptance("kognis-50k", "AC2")
def test_streak_uses_local_dates_of_each_user(api: TestClient, clock: Clock) -> None:
    signup(api, "ann@example.com")
    write(api, "2026-09-01")
    signup(api, "bob@example.com")  # другой пользователь не видит чужую серию
    clock.day = dt.date(2026, 9, 1)
    assert progress(api)["streak"] == 0
    assert progress(api)["xp"] == 0


@pytest.mark.acceptance("kognis-50k", "AC3")
def test_achievements_granted_once_with_date(api: TestClient, clock: Clock) -> None:
    signup(api)
    clock.day = dt.date(2026, 9, 1)
    write(api, "2026-09-01")
    first = progress(api)["achievements"]
    assert [(a["code"], a["earned_on"]) for a in first] == [("first_entry", "2026-09-01")]
    assert first[0]["title"] == "Первая запись"

    for day in (2, 3):
        clock.day = dt.date(2026, 9, day)
        write(api, f"2026-09-0{day}")
        write(api, f"2026-09-0{day}")  # повторные действия ничего не дублируют
    got = {a["code"]: a["earned_on"] for a in progress(api)["achievements"]}
    assert got == {"first_entry": "2026-09-01", "streak_3": "2026-09-03"}


@pytest.mark.acceptance("kognis-50k", "AC3")
def test_ten_day_reviews_achievement(api: TestClient, clock: Clock) -> None:
    signup(api)
    for day in range(1, 10):
        clock.day = dt.date(2026, 9, day)
        review(api, f"2026-09-{day:02d}")
    assert "reviews_10" not in {a["code"] for a in progress(api)["achievements"]}
    clock.day = dt.date(2026, 9, 10)
    review(api, "2026-09-10")
    codes = {a["code"] for a in progress(api)["achievements"]}
    assert {"reviews_10", "streak_7"} <= codes
    assert "first_entry" not in codes  # итоги дня — не записи
