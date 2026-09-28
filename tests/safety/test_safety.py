import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kognis.safety import DISCLAIMER, assess, check_text, help_block

PHRASES = json.loads((Path(__file__).parent / "phrases.json").read_text(encoding="utf-8"))
VALID_PW = "correct horse"


def signup(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": "ann@example.com", "password": VALID_PW}
    )
    assert response.status_code == 201


@pytest.mark.parametrize("text", PHRASES["crisis"])
def test_crisis_phrases_are_detected(text: str) -> None:
    assert assess(text).crisis


@pytest.mark.parametrize("text", PHRASES["normal"])
def test_normal_phrases_are_not_flagged(text: str) -> None:
    assert not assess(text).crisis


def test_help_block_defaults_to_112(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOGNIS_HELP_CONTACTS", raising=False)
    assert [c.phone for c in help_block().contacts] == ["112"]


def test_help_contacts_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOGNIS_HELP_CONTACTS", '[{"name": "Линия", "phone": "8-800"}]')
    assert [(c.name, c.phone) for c in help_block().contacts] == [("Линия", "8-800")]


def test_broken_contacts_config_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOGNIS_HELP_CONTACTS", "не json")
    with pytest.raises(ValueError, match="KOGNIS_HELP_CONTACTS"):
        help_block()


def test_check_text_returns_help_only_for_crisis() -> None:
    assert check_text("хочу умереть")[1] is not None
    assert check_text("хороший день")[1] is None


def test_disclaimer_is_not_medical_help() -> None:
    assert "не медицинская помощь" in DISCLAIMER


@pytest.mark.acceptance("kognis-d5q", "AC1")
@pytest.mark.parametrize("text", PHRASES["crisis"])
def test_crisis_entry_is_saved_with_help_block(client: TestClient, text: str) -> None:
    signup(client)
    response = client.post("/api/entries", json={"text": text})
    assert response.status_code == 201
    body = response.json()
    assert body["crisis"] is True
    assert body["help"]["contacts"][0]["phone"] == "112"
    assert body["help"]["message"]
    listed = client.get("/api/entries").json()
    assert [(e["text"], e["crisis"]) for e in listed] == [(text.strip(), True)]


@pytest.mark.acceptance("kognis-d5q", "AC2")
@pytest.mark.parametrize("text", PHRASES["normal"])
def test_normal_entry_has_no_help_block(client: TestClient, text: str) -> None:
    signup(client)
    body = client.post("/api/entries", json={"text": text}).json()
    assert body["crisis"] is False
    assert body["help"] is None


@pytest.mark.acceptance("kognis-d5q", "AC3")
@pytest.mark.parametrize("text", PHRASES["crisis"])
def test_crisis_text_gives_no_rewards(text: str) -> None:
    assert assess(text).allows_rewards is False


@pytest.mark.acceptance("kognis-d5q", "AC3")
@pytest.mark.parametrize("text", PHRASES["normal"])
def test_normal_text_keeps_rewards(text: str) -> None:
    assert assess(text).allows_rewards is True
