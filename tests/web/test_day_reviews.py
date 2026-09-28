"""Итог дня по HTTP: приёмочные тесты kognis-7cn (AC1–AC3)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from kognis.diary import DayReview, DiaryService
from kognis.web import create_app

VALID_PW = "correct horse"


def signup(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/register", json={"email": email, "password": VALID_PW})
    assert response.status_code == 201


@pytest.mark.acceptance("kognis-7cn", "AC1")
def test_review_saved_and_resave_updates_same_day(client: TestClient) -> None:
    signup(client, "ann@example.com")
    first = client.put(
        "/api/day-reviews/2026-09-01",
        json={"wellbeing": 4, "mood": 6, "reflection": "  Устал, но доволен  "},
    )
    assert first.status_code == 200
    assert first.json()["reflection"] == "Устал, но доволен"

    second = client.put(
        "/api/day-reviews/2026-09-01", json={"wellbeing": 7, "mood": 8, "reflection": "Отдохнул"}
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    client.put("/api/day-reviews/2026-09-02", json={"wellbeing": 5, "mood": 5})
    history = client.get("/api/day-reviews").json()
    assert [(r["date"], r["wellbeing"], r["mood"], r["reflection"]) for r in history] == [
        ("2026-09-02", 5, 5, ""),
        ("2026-09-01", 7, 8, "Отдохнул"),
    ]


@pytest.mark.acceptance("kognis-7cn", "AC2")
@pytest.mark.parametrize(
    "payload",
    [
        {"wellbeing": 0, "mood": 5},
        {"wellbeing": 5, "mood": 11},
        {"wellbeing": -3, "mood": 5},
    ],
)
def test_out_of_range_scale_rejected_with_readable_error(
    client: TestClient, payload: dict[str, int]
) -> None:
    signup(client, "ann@example.com")
    response = client.put("/api/day-reviews/2026-09-01", json=payload)
    assert response.status_code == 422
    assert "от 1 до 10" in response.json()["detail"]
    assert client.get("/api/day-reviews").json() == []


@pytest.mark.acceptance("kognis-7cn", "AC3")
def test_history_visible_only_to_owner(engine: Engine) -> None:
    ann = TestClient(create_app(engine))
    signup(ann, "ann@example.com")
    ann.put("/api/day-reviews/2026-09-01", json={"wellbeing": 3, "mood": 2, "reflection": "тяжело"})

    anonymous = TestClient(create_app(engine))
    assert anonymous.get("/api/day-reviews").status_code == 401
    unauthorized = anonymous.put("/api/day-reviews/2026-09-01", json={"wellbeing": 1, "mood": 1})
    assert unauthorized.status_code == 401

    bob = TestClient(create_app(engine))
    signup(bob, "bob@example.com")
    assert bob.get("/api/day-reviews").json() == []
    # тот же день у другого пользователя — отдельный итог, чужой не затронут
    bob.put("/api/day-reviews/2026-09-01", json={"wellbeing": 9, "mood": 9})
    assert ann.get("/api/day-reviews").json()[0]["reflection"] == "тяжело"
    assert len(bob.get("/api/day-reviews").json()) == 1


@pytest.mark.parametrize("bad", [None, True, "5", 5.5])
def test_non_integer_scale_rejected(client: TestClient, bad: object) -> None:
    signup(client, "ann@example.com")
    response = client.put("/api/day-reviews/2026-09-01", json={"wellbeing": bad, "mood": 5})
    assert response.status_code == 422
    assert client.get("/api/day-reviews").json() == []


def test_concurrent_save_loses_race_then_updates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Гонка двух сохранений за один день: первая попытка ловит нарушение уникальности
    (это делает БД при одновременной вставке), вторая обновляет существующий итог — не 500."""
    signup(client, "ann@example.com")
    client.put("/api/day-reviews/2026-09-01", json={"wellbeing": 5, "mood": 5})
    real = DiaryService.save_day_review
    calls: list[int] = []

    def flaky(self: DiaryService, *args: Any) -> DayReview:
        calls.append(1)
        if len(calls) == 1:
            raise IntegrityError("insert", {}, Exception("uq_day_reviews_owner_date"))
        return real(self, *args)

    monkeypatch.setattr(DiaryService, "save_day_review", flaky)
    response = client.put("/api/day-reviews/2026-09-01", json={"wellbeing": 9, "mood": 9})
    assert response.status_code == 200
    assert [r["wellbeing"] for r in client.get("/api/day-reviews").json()] == [9]


def test_reflection_too_long_rejected(client: TestClient) -> None:
    signup(client, "ann@example.com")
    response = client.put(
        "/api/day-reviews/2026-09-01", json={"wellbeing": 5, "mood": 5, "reflection": "x" * 5001}
    )
    assert response.status_code == 422
