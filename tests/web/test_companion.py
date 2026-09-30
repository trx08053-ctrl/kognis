"""Цифровые герои по HTTP: приёмочные kognis-zjg AC2 (открытка) и AC3 (наставники); IDOR."""

import datetime as dt
import json
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

PW = "correct horse"


class Clock:
    def __init__(self, day: dt.date) -> None:
        self.day = day

    def __call__(self) -> dt.datetime:
        return dt.datetime.combine(self.day, dt.time(12), dt.UTC)


class Analyst:
    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        return json.dumps(
            {"summary": "Неделя.", "patterns": [], "questions": [], "quest_ideas": []}
        )


@pytest.fixture
def clock() -> Clock:
    return Clock(dt.date(2026, 9, 1))


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    client = TestClient(create_app(engine, clock=clock, ai_provider=Analyst()))
    assert client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": PW}
    ).is_success
    return client


def register(client: TestClient, email: str) -> None:
    body = {"email": email, "password": PW}
    assert client.post("/api/auth/register", json=body).is_success


def meet(client: TestClient, address: str = "ty") -> dict[str, Any]:
    r = client.put("/api/companion", json={"appearance": "fox", "name": "Луна", "address": address})
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    return body


def get(client: TestClient) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/companion").json()
    return body


def review(client: TestClient, clock: Clock, day: dt.date) -> None:
    clock.day = day
    assert client.put(f"/api/day-reviews/{day}", json={"wellbeing": 5, "mood": 5}).is_success


def test_companion_requires_login(engine: Engine) -> None:
    anon = TestClient(create_app(engine))
    assert anon.get("/api/companion").status_code == 401
    assert anon.put("/api/companion", json={}).status_code == 401


def test_first_visit_offers_intro_then_companion_is_chosen(api: TestClient) -> None:
    first = get(api)
    assert first["chosen"] is False
    assert first["line"] == {"hero": "companion", "situation": "intro"}
    done = meet(api, "vy")
    assert (done["chosen"], done["name"], done["address"], done["stage"]) == (True, "Луна", "vy", 1)
    assert done["line"] is None  # знакомство не считается новой стадией


def test_invalid_choice_is_rejected_with_code(api: TestClient) -> None:
    r = api.put("/api/companion", json={"appearance": "dragon", "name": "Луна", "address": "ty"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "heroes.appearance_unknown"


@pytest.mark.acceptance("kognis-zjg", "AC2")
def test_postcard_arrives_next_day_after_day_review_one_per_day(
    api: TestClient, clock: Clock
) -> None:
    meet(api)
    day = clock.day
    review(api, clock, day)
    assert get(api)["postcard"] is None  # в тот же день спутник только уходит в путешествие
    clock.day = day + dt.timedelta(days=1)
    card = get(api)["postcard"]
    assert card is not None
    assert card["for_day"] == day.isoformat()
    assert get(api)["postcard"] == card  # повторный вход в тот же день — та же открытка
    clock.day = day + dt.timedelta(days=2)
    assert get(api)["postcard"] is None  # новый итог дня — новая открытка, не раньше


@pytest.mark.acceptance("kognis-zjg", "AC2")
def test_no_postcard_without_day_review(api: TestClient, clock: Clock) -> None:
    meet(api)
    assert api.post(
        "/api/entries", json={"text": "Запись", "date": clock.day.isoformat()}
    ).is_success
    clock.day += dt.timedelta(days=1)
    assert get(api)["postcard"] is None


@pytest.mark.acceptance("kognis-zjg", "AC3")
def test_mentor_opens_by_analysis_direction_or_library_quest(api: TestClient, clock: Clock) -> None:
    locked = {m["code"]: m["unlocked"] for m in get(api)["mentors"]}
    assert locked == {"analyst": False, "guide": False, "gardener": False, "mechanic": False}
    day = clock.day.isoformat()
    assert api.post("/api/entries", json={"text": "Было тревожно", "date": day}).is_success
    period = {"consent": True, "start": day, "end": day, "direction": "cbt"}
    assert api.post("/api/analyses", json=period).is_success
    assert api.post("/api/quests", json={"template": "activation_5"}).is_success
    opened = {m["code"]: m["direction"] for m in get(api)["mentors"] if m["unlocked"]}
    assert opened == {"analyst": "cbt", "mechanic": "activation"}


def test_companion_is_per_user(engine: Engine, clock: Clock, api: TestClient) -> None:
    meet(api)
    other = TestClient(create_app(engine, clock=clock))
    assert other.post(
        "/api/auth/register", json={"email": "b@example.com", "password": PW}
    ).is_success
    assert get(other)["chosen"] is False


def write_days(client: TestClient, clock: Clock, count: int) -> None:
    start = clock.day
    for n in range(count):
        clock.day = start + dt.timedelta(days=n)
        entry = {"text": "Запись", "date": clock.day.isoformat()}
        assert client.post("/api/entries", json=entry).is_success


def test_new_stage_line_is_shown_until_seen_and_choice_can_change(
    api: TestClient, clock: Clock
) -> None:
    meet(api)
    write_days(api, clock, 7)  # 7 дней с дневником — вторая стадия
    state = get(api)
    assert (state["stage"], state["days_total"], state["days_to_next"]) == (2, 7, 14)
    assert state["line"] == {"hero": "companion", "situation": "new_stage"}
    assert api.post("/api/companion/seen", json={}).json()["line"] is None
    change = {"appearance": "owl", "name": "Сова", "address": "vy"}
    renamed = api.put("/api/companion", json=change).json()
    assert (renamed["appearance"], renamed["name"], renamed["stage"]) == ("owl", "Сова", 2)


def test_pause_rests_the_companion_without_regress(api: TestClient, clock: Clock) -> None:
    meet(api)
    write_days(api, clock, 7)
    api.post("/api/companion/seen", json={})
    clock.day += dt.timedelta(days=60)
    state = get(api)
    assert (state["stage"], state["resting"]) == (2, True)
    assert state["line"] == {"hero": "companion", "situation": "return"}
