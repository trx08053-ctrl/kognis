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

    def __call__(self) -> dt.datetime:
        return dt.datetime.combine(self.day, dt.time(12), dt.UTC)  # полдень UTC — та же дата в МСК


CLOCKS: list[Clock] = []  # «сегодня» текущего теста: write/review по умолчанию пишут «в этот день»


@pytest.fixture
def clock() -> Clock:
    current = Clock(dt.date(2026, 9, 1))
    CLOCKS[:] = [current]
    return current


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    return TestClient(create_app(engine, clock=clock))


def signup(client: TestClient, email: str = "ann@example.com") -> None:
    response = client.post("/api/auth/register", json={"email": email, "password": VALID_PW})
    assert response.status_code == 201


def at(day: str, *, live: bool = True) -> None:
    """Пользователь действует в этот день (live) — «сегодня» совпадает с датой действия."""
    if live:
        CLOCKS[0].day = dt.date.fromisoformat(day)


def write(client: TestClient, day: str, text: str = "Хороший день", *, live: bool = True) -> None:
    at(day, live=live)
    response = client.post("/api/entries", json={"text": text, "date": day})
    assert response.status_code == 201


def progress(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/progress")
    assert response.status_code == 200
    return response.json()


def review(client: TestClient, day: str, *, live: bool = True) -> None:
    at(day, live=live)
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
        # мотивация 2.0 (kognis-3r1): запас заморозок, цель недели и показатели дней
        "best_streak": 0,
        "freezes": 2,
        "days_30": 0,
        "days_total": 0,
        "weekly_goal": 3,
        "week_days": 0,
        "weekend_days": [],
        "recovery": None,
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
def test_crisis_entry_gives_no_xp(api: TestClient, crisis_on: None) -> None:
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
def test_freeze_stock_bridges_missed_days_until_it_runs_out(api: TestClient, clock: Clock) -> None:
    # правило заменено в kognis-3r1: вместо одной заморозки на ISO-неделю — запас из двух заморозок
    signup(api)
    # 2026-09-07 — понедельник. Пн, вт, (ср пропуск), чт: заморозка гасит пропуск
    for day in ("2026-09-07", "2026-09-08", "2026-09-10"):
        write(api, day)
    clock.day = dt.date(2026, 9, 10)
    assert progress(api)["streak"] == 3

    write(api, "2026-09-12")  # пт пропущен: вторая заморозка из запаса, серия продолжается
    clock.day = dt.date(2026, 9, 12)
    state = progress(api)
    assert (state["streak"], state["freezes"]) == (4, 0)

    write(api, "2026-09-15")  # вс и пн пропущены, запас пуст: серия начинается заново
    clock.day = dt.date(2026, 9, 15)
    assert progress(api)["streak"] == 1


@pytest.mark.acceptance("kognis-50k", "AC2")
def test_progress_is_private_to_each_user(api: TestClient) -> None:
    signup(api, "ann@example.com")
    write(api, "2026-09-01")
    signup(api, "bob@example.com")  # другой пользователь не видит чужую серию и опыт
    state = progress(api)
    assert (state["streak"], state["xp"], state["achievements"]) == (0, 0, [])


@pytest.mark.acceptance("kognis-50k", "AC2")
def test_future_and_old_dates_give_no_xp_or_streak(api: TestClient, clock: Clock) -> None:
    signup(api)
    clock.day = dt.date(2026, 9, 10)
    write(api, "2026-09-11", live=False)  # будущее
    write(api, "2026-09-02", live=False)  # старше недели: задним числом опыт не копится
    review(api, "2026-09-11", live=False)
    review(api, "2026-09-02", live=False)
    state = progress(api)
    assert (state["xp"], state["streak"], state["achievements"]) == (0, 0, [])

    write(api, "2026-09-03", live=False)  # ровно неделя назад — ещё можно
    assert progress(api)["xp"] == 10


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
