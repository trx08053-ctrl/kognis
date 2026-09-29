"""Часовой пояс пользователя — единый источник «сегодня»: приёмочные тесты kognis-1yv."""

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
# в UTC ещё 1 сентября, во Владивостоке (UTC+10) уже 2 сентября, 06:00
NOW = dt.datetime(2026, 9, 1, 20, 0, tzinfo=dt.UTC)


class EmptyAnalysis:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        self.sent.append(messages[0].content)
        return json.dumps({"summary": "Итог.", "patterns": [], "questions": [], "quest_ideas": []})


def make(engine: Engine, provider: EmptyAnalysis | None = None) -> TestClient:
    return TestClient(create_app(engine, clock=lambda: NOW, ai_provider=provider))


def register(client: TestClient, timezone: str | None, email: str = "ann@example.com") -> Any:
    body: dict[str, Any] = {"email": email, "password": PW}
    if timezone is not None:
        body["timezone"] = timezone
    return client.post("/api/auth/register", json=body)


@pytest.mark.acceptance("kognis-1yv", "AC1")
def test_entry_gets_local_date_and_analysis_includes_it(engine: Engine) -> None:
    provider = EmptyAnalysis()
    client = make(engine, provider)
    assert register(client, "Asia/Vladivostok").status_code == 201
    me = client.get("/api/me").json()
    assert me["today"] == "2026-09-02"  # в UTC ещё 2026-09-01

    entry = client.post("/api/entries", json={"text": "утренняя запись про работу"})
    assert entry.status_code == 201
    assert entry.json()["date"] == "2026-09-02"

    period = {"start": "2026-08-27", "end": me["today"]}  # «за неделю» от сегодня пользователя
    r = client.post("/api/analyses", json={"direction": "cbt", "consent": True, **period})
    assert r.status_code == 201
    assert "утренняя запись про работу" in provider.sent[0]


@pytest.mark.acceptance("kognis-1yv", "AC1")
def test_each_user_has_own_today(engine: Engine) -> None:
    moscow = make(engine)
    assert register(moscow, None).status_code == 201  # по умолчанию Europe/Moscow (UTC+3)
    assert moscow.get("/api/me").json()["today"] == "2026-09-01"
    honolulu = make(engine)
    assert register(honolulu, "Pacific/Honolulu", "bob@example.com").status_code == 201
    assert honolulu.get("/api/me").json()["today"] == "2026-09-01"
    tokyo = make(engine)
    assert register(tokyo, "Asia/Tokyo", "cat@example.com").status_code == 201
    assert tokyo.get("/api/me").json()["today"] == "2026-09-02"


@pytest.mark.acceptance("kognis-1yv", "AC3")
def test_timezone_saved_on_register_and_changed_in_profile(engine: Engine) -> None:
    client = make(engine)
    r = register(client, "America/New_York")
    assert r.status_code == 201
    assert r.json()["timezone"] == "America/New_York"
    assert client.get("/api/me").json()["timezone"] == "America/New_York"

    changed = client.put("/api/me/settings", json={"timezone": "Asia/Vladivostok"})
    assert changed.status_code == 200
    assert changed.json()["timezone"] == "Asia/Vladivostok"
    assert changed.json()["today"] == "2026-09-02"
    me = client.get("/api/me").json()
    assert (me["timezone"], me["advanced"]) == ("Asia/Vladivostok", False)

    # режим интерфейса меняется отдельно и пояс не трогает
    assert client.put("/api/me/settings", json={"advanced": True}).json()["timezone"] == (
        "Asia/Vladivostok"
    )


@pytest.mark.acceptance("kognis-1yv", "AC3")
@pytest.mark.parametrize("bad", ["Mars/Base", "", " Europe/Moscow", "../etc/passwd", "x" * 100])
def test_unknown_timezone_is_rejected(engine: Engine, bad: str) -> None:
    client = make(engine)
    assert register(client, bad, "bad@example.com").status_code == 422
    assert register(client, "Europe/Moscow").status_code == 201
    r = client.put("/api/me/settings", json={"timezone": bad})
    assert r.status_code == 422
    assert client.get("/api/me").json()["timezone"] == "Europe/Moscow"
