"""Кризисный детектор отключён по умолчанию: приёмочные тесты kognis-xci (AC1–AC3, AC5)."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.analysis._app import SYSTEM_PROMPT
from kognis.analysis._prompts_i18n import SAFETY_CLAUSE
from kognis.safety import check_text, crisis_detector_enabled
from kognis.web import create_app

ROOT = Path(__file__).resolve().parents[2]
CRISIS_ENTRY = "хочу умереть"
PERIOD = {"start": "2026-09-01", "end": "2026-09-07"}


class ScriptedProvider:
    """Отвечает заготовленными ответами и запоминает вызовы."""

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: list[tuple[str, list[Message]]] = []

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        self.calls.append((system, list(messages)))
        return self.replies.pop(0)


def good(entry_ids: list[int]) -> str:
    pattern = {"title": "Тема", "description": "Описание", "entry_ids": entry_ids, "quotes": []}
    return json.dumps({"summary": "Итог периода.", "patterns": [pattern], "questions": []})


def make(engine: Engine, provider: ScriptedProvider) -> TestClient:
    client = TestClient(create_app(engine, ai_provider=provider))
    r = client.post(
        "/api/auth/register", json={"email": "ann@example.com", "password": "correct horse"}
    )
    assert r.status_code == 201
    return client


def add_entry(client: TestClient, text: str) -> int:
    r = client.post("/api/entries", json={"text": text, "date": "2026-09-02"})
    assert r.status_code == 201
    return int(r.json()["id"])


def analyze(client: TestClient) -> Any:
    return client.post("/api/analyses", json={"direction": "cbt", "consent": True, **PERIOD})


@pytest.mark.acceptance("kognis-xci", "AC1")
def test_detector_is_off_by_default_and_entry_is_saved_without_crisis(engine: Engine) -> None:
    assert crisis_detector_enabled() is False
    assert check_text(CRISIS_ENTRY)[0].crisis is False
    provider = ScriptedProvider()
    client = make(engine, provider)
    r = client.post("/api/entries", json={"text": CRISIS_ENTRY, "date": "2026-09-02"})
    assert r.status_code == 201
    saved = r.json()
    assert saved["crisis"] is False
    assert saved["help"] is None
    provider.replies.append(good([saved["id"]]))
    analysis = analyze(client)
    assert analysis.status_code == 201
    body = analysis.json()
    assert body["status"] == "done"
    assert body["help"] is None
    assert len(provider.calls) == 1
    assert CRISIS_ENTRY in provider.calls[0][1][0].content


@pytest.mark.acceptance("kognis-xci", "AC1")
def test_quiz_and_day_review_with_crisis_phrase_are_ordinary_when_off(engine: Engine) -> None:
    client = make(engine, ScriptedProvider())
    review = client.put(
        "/api/day-reviews/2026-09-02",
        json={"wellbeing": 2, "mood": 2, "reflection": CRISIS_ENTRY},
    )
    assert review.status_code == 200
    assert review.json()["help"] is None


@pytest.mark.acceptance("kognis-xci", "AC2")
def test_detector_on_gives_help_and_skips_provider(engine: Engine, crisis_on: None) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    saved = client.post("/api/entries", json={"text": CRISIS_ENTRY, "date": "2026-09-02"}).json()
    assert saved["crisis"] is True
    assert saved["help"]["contacts"][0]["phone"] == "112"
    body = analyze(client).json()
    assert body["status"] == "crisis"
    assert body["help"] is not None
    assert provider.calls == []


@pytest.mark.acceptance("kognis-xci", "AC3")
def test_prompt_tells_model_what_to_do_about_threat_to_life(engine: Engine) -> None:
    for text in (SAFETY_CLAUSE, SYSTEM_PROMPT):
        assert "угроза жизни или здоровью" in text
        assert "не разбирай это как обычный паттерн" in text
        assert "близкому человеку" in text
        assert "экстренные службы своей страны" in text
        assert "диагнозов не ставь" in text
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client, CRISIS_ENTRY)
    provider.replies.append(good([eid]))
    assert analyze(client).status_code == 201
    assert "угроза жизни или здоровью" in provider.calls[0][0]


@pytest.mark.acceptance("kognis-xci", "AC5")
def test_followup_task_exists_and_architecture_links_the_risk() -> None:
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    row = next(line for line in architecture.splitlines() if line.startswith("| R4 |"))
    task_id = "kognis-fvn"
    assert task_id in row
    issues = [
        json.loads(line)
        for line in (ROOT / ".beads" / "issues.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    task = next(i for i in issues if i["id"] == task_id)
    assert "Включить кризисный детектор по языкам" in task["title"]
