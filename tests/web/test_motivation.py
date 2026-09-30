"""Мотивация 2.0 по HTTP: недельная цель, выходные, восстановление (kognis-3r1, AC2)."""

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

from .test_gameplay import CLOCKS, Clock, at, progress, signup, write

MON = "2026-09-07"  # понедельник


@pytest.fixture
def clock() -> Clock:
    current = Clock(dt.date(2026, 9, 1))
    CLOCKS[:] = [current]  # `at` и `write` двигают «сегодня» этого теста
    return current


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    return TestClient(create_app(engine, clock=clock))


def put_settings(client: TestClient, weekend: list[int], goal: int) -> dict[str, Any]:
    body = {"weekend_days": weekend, "weekly_goal": goal}
    response = client.put("/api/progress/settings", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_new_user_defaults(api: TestClient) -> None:
    signup(api)
    data = progress(api)
    assert (data["weekly_goal"], data["weekend_days"], data["freezes"], data["recovery"]) == (
        3,
        [],
        2,
        None,
    )
    assert (data["days_30"], data["days_total"], data["best_streak"]) == (0, 0, 0)


@pytest.mark.acceptance("kognis-3r1", "AC2")
def test_weekly_goal_is_chosen_counted_and_rewarded_once_per_week(api: TestClient) -> None:
    signup(api)
    assert put_settings(api, [], 5)["weekly_goal"] == 5
    for day in ("2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10"):
        write(api, day)
    mid = progress(api)
    assert (mid["week_days"], mid["xp"]) == (
        4,
        40,
    )  # цель 5 дней ещё не достигнута, ничего не отнято
    write(api, "2026-09-11")
    done = progress(api)
    assert (done["week_days"], done["xp"]) == (5, 50 + 30)  # 5 записей + бонус недели
    write(api, "2026-09-12")
    assert progress(api)["xp"] == 90  # ещё +10 за запись, бонус повторно не выдаётся
    write(api, "2026-09-14")  # новая неделя: счёт начался заново, бонус снова возможен позже
    fresh = progress(api)
    assert (fresh["week_days"], fresh["xp"]) == (1, 100)


@pytest.mark.acceptance("kognis-3r1", "AC2")
def test_missed_goal_is_not_punished(api: TestClient) -> None:
    signup(api)
    write(api, MON)
    write(api, "2026-09-14")
    data = progress(api)
    assert data["xp"] == 20  # цель 3 не выполнена — XP не убавился
    assert data["week_days"] == 1


@pytest.mark.acceptance("kognis-3r1", "AC2")
def test_lowering_the_goal_awards_the_week_bonus_once(api: TestClient) -> None:
    signup(api)
    put_settings(api, [], 5)
    for day in ("2026-09-07", "2026-09-08", "2026-09-09"):
        write(api, day)
    assert progress(api)["xp"] == 30
    assert put_settings(api, [], 3)["xp"] == 60
    assert put_settings(api, [], 3)["xp"] == 60


def test_settings_are_validated(api: TestClient) -> None:
    signup(api)
    bad: list[dict[str, Any]] = [
        {"weekend_days": [], "weekly_goal": 4},
        {"weekend_days": [5, 6, 0], "weekly_goal": 3},
        {"weekend_days": [7], "weekly_goal": 3},
    ]
    for body in bad:
        response = api.put("/api/progress/settings", json=body)
        assert response.status_code == 422
        assert response.json()["detail"]["code"].startswith("progress.")
    assert put_settings(api, [5, 5], 7)["weekend_days"] == [5]


@pytest.mark.acceptance("kognis-3r1", "AC2")
def test_weekend_day_does_not_break_the_streak(api: TestClient) -> None:
    signup(api)
    put_settings(api, [5, 6], 3)
    write(api, "2026-09-11")  # пятница
    write(api, "2026-09-14")  # понедельник: сб и вс не пропуск
    data = progress(api)
    assert (data["streak"], data["freezes"]) == (2, 2)


def break_the_streak(api: TestClient) -> None:
    for day in ("2026-09-07", "2026-09-08", "2026-09-09"):
        write(api, day)
    at("2026-09-13")  # пропущены чт, пт — заморозки; сб — обрыв


@pytest.mark.acceptance("kognis-3r1", "AC2")
def test_recovery_offer_and_note_restore_the_streak_once(api: TestClient) -> None:
    signup(api)
    break_the_streak(api)
    data = progress(api)
    assert data["streak"] == 0
    assert data["best_streak"] == 3
    assert data["recovery"] == {
        "streak_before": 3,
        "broken_on": "2026-09-12",
        "expires_on": "2026-09-15",
    }
    xp_before = data["xp"]
    response = api.post("/api/progress/recovery", json={"note": "Заболел"})
    assert response.status_code == 200
    restored = response.json()
    assert (restored["streak"], restored["recovery"], restored["xp"]) == (3, None, xp_before)
    again = api.post("/api/progress/recovery", json={"note": "Ещё раз"})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "progress.recovery_unavailable"


@pytest.mark.acceptance("kognis-3r1", "AC2")
def test_recovery_after_72_hours_is_unavailable(api: TestClient) -> None:
    signup(api)
    break_the_streak(api)
    at("2026-09-16")  # обрыв 12-го, окно до 15-го
    assert progress(api)["recovery"] is None
    response = api.post("/api/progress/recovery", json={"note": "Поздно"})
    assert response.status_code == 409


def test_recovery_note_is_limited_and_needs_login(api: TestClient) -> None:
    assert api.post("/api/progress/recovery", json={"note": "x"}).status_code == 401
    signup(api)
    assert api.post("/api/progress/recovery", json={"note": ""}).status_code == 422
    assert api.post("/api/progress/recovery", json={"note": "я" * 501}).status_code == 422
    assert (
        api.put("/api/progress/settings", json={"weekend_days": [], "weekly_goal": 3}).status_code
        == 200
    )
