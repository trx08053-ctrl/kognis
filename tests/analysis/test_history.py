"""История разборов: постраничный список и удаление (kognis-qkh AC2, AC4) через HTTP API."""

import datetime as dt
import itertools
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
        data = json.loads(messages[0].content)
        ids = [e["id"] for e in data.get("entries", [])] or [
            i for p in data["previous_result"]["patterns"] for i in p["entry_ids"]
        ]
        return json.dumps(
            {
                "summary": f"Разбор {self.count}",
                "patterns": [
                    {
                        "title": "Избегание",
                        "description": "Откладываешь звонки.",
                        "entry_ids": ids,
                        "quotes": ["не хочется звонить"],
                    }
                ],
                "questions": ["Что помогло?"],
                "quest_ideas": [],
            }
        )


def signed_in(engine: Engine, email: str) -> TestClient:
    client = TestClient(create_app(engine, ai_provider=Numbered()))
    r = client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return client


_periods = itertools.count()


def analyze(client: TestClient) -> dict[str, Any]:
    # повтор направления и периода — 409 (kognis-sky), поэтому конец периода каждый раз новый
    end = dt.date.fromisoformat(PERIOD["end"]) + dt.timedelta(days=next(_periods))
    r = client.post(
        "/api/analyses", json={"direction": "cbt", "consent": True, **PERIOD, "end": str(end)}
    )
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
    made = analyze(ann)
    item = ann.get("/api/analyses").json()[0]
    assert item["created_at"].endswith("Z") or "+00:00" in item["created_at"]
    # конец периода в analyze() сдвигается (дубли — 409), начало и направление — как в запросе
    assert (item["start"], item["end"], item["direction"], item["status"]) == (
        PERIOD["start"],
        made["end"],
        "cbt",
        "done",
    )
    assert item["end"] >= PERIOD["end"]


@pytest.mark.acceptance("kognis-qkh", "AC2")
@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 10**30}, {"limit": "x"}]
)
def test_history_rejects_bad_paging(ann: TestClient, params: dict[str, Any]) -> None:
    assert ann.get("/api/analyses", params=params).status_code == 422


@pytest.mark.acceptance("kognis-qkh", "AC3")
def test_reopened_analysis_has_patterns_quotes_questions_and_follow_up(ann: TestClient) -> None:
    first = analyze(ann)
    follow = ann.post(
        f"/api/analyses/{first['id']}/answers",
        json={"answers": ["Позвонить утром"], "consent": True},
    )
    assert follow.status_code == 201, follow.text
    analyze(ann)  # более новый разбор не подменяет старые

    opened = ann.get(f"/api/analyses/{first['id']}").json()
    assert opened["patterns"][0]["title"] == "Избегание"
    assert opened["patterns"][0]["quotes"] == ["не хочется звонить"]
    assert opened["patterns"][0]["entry_ids"]
    assert opened["questions"] == ["Что помогло?"]

    reopened = ann.get(f"/api/analyses/{follow.json()['id']}").json()
    assert reopened["answers"] == ["Позвонить утром"]
    assert reopened["parent_id"] == first["id"]
    assert reopened["patterns"][0]["quotes"] == ["не хочется звонить"]


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
