"""История разборов: постраничный список и удаление (kognis-qkh AC2, AC4) через HTTP API."""

import json
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

PW = "correct horse"
PERIOD = {"start": "2026-09-01", "end": "2026-09-07"}


class Numbered:
    """Каждый ответ модели — с новым резюме («Разбор 1», «Разбор 2», …)."""

    def __init__(self) -> None:
        self.count = 0

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        self.count += 1
        return json.dumps(
            {
                "summary": f"Разбор {self.count}",
                "patterns": [],
                "questions": ["Что помогло?"],
                "quest_ideas": [],
            }
        )


def signed_in(engine: Engine, email: str) -> TestClient:
    client = TestClient(create_app(engine, ai_provider=Numbered()))
    r = client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return client


def analyze(client: TestClient) -> dict[str, Any]:
    r = client.post("/api/analyses", json={"direction": "cbt", "consent": True, **PERIOD})
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def remove(client: TestClient, analysis_id: int) -> Any:
    """DELETE с JSON-телом: изменяющие запросы принимаются только как JSON (защита от CSRF)."""
    return client.request("DELETE", f"/api/analyses/{analysis_id}", json={})


@pytest.fixture
def ann(engine: Engine) -> TestClient:
    client = signed_in(engine, "ann@example.com")
    client.post("/api/entries", json={"text": "не хочется звонить", "date": "2026-09-02"})
    return client


@pytest.mark.acceptance("kognis-qkh", "AC2")
def test_history_is_paged_newest_first(ann: TestClient) -> None:
    ids = [analyze(ann)["id"] for _ in range(5)]

    first = ann.get("/api/analyses", params={"limit": 2})
    assert [a["id"] for a in first.json()] == [ids[4], ids[3]]
    assert first.headers["X-Next-Cursor"] == "2"

    second = ann.get("/api/analyses", params={"limit": 2, "offset": 2})
    assert [a["id"] for a in second.json()] == [ids[2], ids[1]]
    assert second.headers["X-Next-Cursor"] == "4"

    last = ann.get("/api/analyses", params={"limit": 2, "offset": 4})
    assert [a["id"] for a in last.json()] == [ids[0]]
    assert "X-Next-Cursor" not in last.headers


@pytest.mark.acceptance("kognis-qkh", "AC2")
def test_history_items_have_date_period_direction_status(ann: TestClient) -> None:
    analyze(ann)
    item = ann.get("/api/analyses").json()[0]
    assert item["created_at"].endswith("Z") or "+00:00" in item["created_at"]
    assert (item["start"], item["end"], item["direction"], item["status"]) == (
        "2026-09-01",
        "2026-09-07",
        "cbt",
        "done",
    )


@pytest.mark.acceptance("kognis-qkh", "AC2")
@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 10**30}, {"limit": "x"}]
)
def test_history_rejects_bad_paging(ann: TestClient, params: dict[str, Any]) -> None:
    assert ann.get("/api/analyses", params=params).status_code == 422


@pytest.mark.acceptance("kognis-qkh", "AC4")
def test_delete_own_analysis(ann: TestClient) -> None:
    keep, gone = analyze(ann)["id"], analyze(ann)["id"]

    assert remove(ann, gone).status_code == 204

    assert ann.get(f"/api/analyses/{gone}").status_code == 404
    assert [a["id"] for a in ann.get("/api/analyses").json()] == [keep]
    assert remove(ann, gone).status_code == 404


@pytest.mark.acceptance("kognis-qkh", "AC4")
def test_delete_foreign_or_missing_analysis_is_404(engine: Engine, ann: TestClient) -> None:
    mine = analyze(ann)["id"]
    eve = signed_in(engine, "eve@example.com")

    assert remove(eve, mine).status_code == 404
    assert remove(eve, 999999).status_code == 404
    assert ann.get(f"/api/analyses/{mine}").status_code == 200


def test_delete_requires_login(engine: Engine) -> None:
    anonymous = TestClient(create_app(engine))
    assert remove(anonymous, 1).status_code == 401
