"""Кризисный сигнал в рефлексии итога дня: приёмочные тесты kognis-cdu (AC1–AC2)."""

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

VALID_PW = "correct horse"
DAY = dt.date(2026, 9, 1)
CRISIS_TEXT = "Сегодня я не хочу больше жить"


@pytest.fixture
def api(engine: Engine) -> TestClient:
    client = TestClient(create_app(engine, today=lambda: DAY))
    response = client.post(
        "/api/auth/register", json={"email": "ann@example.com", "password": VALID_PW}
    )
    assert response.status_code == 201
    return client


def save_review(client: TestClient, reflection: str, day: str = "2026-09-01") -> dict[str, Any]:
    response = client.put(
        f"/api/day-reviews/{day}", json={"wellbeing": 3, "mood": 3, "reflection": reflection}
    )
    assert response.status_code == 200
    return response.json()


def xp(client: TestClient) -> int:
    return client.get("/api/progress").json()["xp"]


@pytest.mark.acceptance("kognis-cdu", "AC1")
def test_crisis_reflection_saved_with_help_block(api: TestClient) -> None:
    body = save_review(api, CRISIS_TEXT)
    assert body["reflection"] == CRISIS_TEXT
    assert body["help"]["contacts"][0]["phone"] == "112"
    assert [r["reflection"] for r in api.get("/api/day-reviews").json()] == [CRISIS_TEXT]


@pytest.mark.acceptance("kognis-cdu", "AC1")
def test_ordinary_reflection_has_no_help_block(api: TestClient) -> None:
    assert (
        save_review(api, "Хороший день, не хочу жить в этом городе, но работа радует")["help"]
        is None
    )


@pytest.mark.acceptance("kognis-cdu", "AC2")
def test_crisis_reflection_gives_no_xp_ordinary_gives_twenty(api: TestClient) -> None:
    save_review(api, CRISIS_TEXT, "2026-09-01")
    assert xp(api) == 0
    save_review(api, "Спокойный день")  # тот же итог, переписанный без сигнала
    assert xp(api) == 20


@pytest.mark.acceptance("kognis-cdu", "AC2")
def test_crisis_entry_still_gives_no_xp(api: TestClient) -> None:
    response = api.post("/api/entries", json={"text": CRISIS_TEXT, "date": "2026-09-01"})
    assert response.status_code == 201
    assert response.json()["crisis"] is True
    assert xp(api) == 0
