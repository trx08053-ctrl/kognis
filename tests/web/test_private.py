"""Приватные записи: приёмочные тесты kognis-8f1 на стороне сервера (AC1–AC3).

Шифрование выполняет браузер; сервер получает готовый конверт. Здесь конверт собран «как из
браузера»: тот же формат (v, kdf, iter, salt, iv, ct), но шифртекст — случайные байты: сервер
не должен ни читать, ни проверять содержимое, только форму.
"""

import base64
import datetime as dt
import os
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

VALID_PW = "correct horse"
OPEN_TEXT = "Секретная мысль про начальника"
DAY = dt.date(2026, 9, 1)


def b64(size: int) -> str:
    return base64.b64encode(os.urandom(size)).decode()


def envelope(**over: Any) -> dict[str, Any]:
    return {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iter": 600_000,
        "salt": b64(16),
        "iv": b64(12),
        "ct": b64(48),
    } | over


class Recorder:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        self.sent.extend(m.content for m in messages)
        return '{"summary": "ок", "patterns": [], "questions": [], "quest_ideas": []}'


@pytest.fixture
def provider() -> Recorder:
    return Recorder()


@pytest.fixture
def api(engine: Engine, provider: Recorder) -> TestClient:
    client = TestClient(create_app(engine, today=lambda: DAY, ai_provider=provider))
    email = "ann@example.com"
    assert (
        client.post("/api/auth/register", json={"email": email, "password": VALID_PW}).status_code
        == 201
    )
    return client


def create_private(client: TestClient, env: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.post(
        "/api/entries",
        json={"protection": "private", "cipher": env or envelope(), "tags": ["работа"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.acceptance("kognis-8f1", "AC1")
def test_server_stores_only_ciphertext(api: TestClient, engine: Engine) -> None:
    env = envelope()
    created = create_private(api, env)
    assert created["protection"] == "private"
    assert created["text"] == ""
    with engine.connect() as conn:
        row = conn.execute(sql("SELECT text, protection, private_envelope FROM entries")).one()
    assert row.text == ""
    assert row.protection == "private"
    assert env["ct"] in str(row.private_envelope)
    # текста с сервера не видно ни в списке, ни по id
    assert api.get("/api/entries").json()[0]["text"] == ""
    # серверу нельзя прислать открытый текст под видом приватной записи
    leaked = api.post(
        "/api/entries", json={"protection": "private", "cipher": env, "text": OPEN_TEXT}
    )
    assert leaked.status_code == 422
    assert OPEN_TEXT not in leaked.text


@pytest.mark.acceptance("kognis-8f1", "AC2")
def test_envelope_returned_intact_for_decryption_in_browser(api: TestClient) -> None:
    env = envelope()
    created = create_private(api, env)
    for got in (api.get(f"/api/entries/{created['id']}").json(), api.get("/api/entries").json()[0]):
        assert got["cipher"] == env
    # чужой пользователь конверт не получает
    other = TestClient(api.app)
    other.post("/api/auth/register", json={"email": "eve@example.com", "password": VALID_PW})
    assert other.get(f"/api/entries/{created['id']}").status_code == 404


@pytest.mark.acceptance("kognis-8f1", "AC3")
def test_private_entries_never_reach_analysis(api: TestClient, provider: Recorder) -> None:
    env = envelope()
    create_private(api, env)
    api.post("/api/entries", json={"text": "обычная запись про сон", "tags": ["сон"]})
    response = api.post(
        "/api/analyses",
        json={"direction": "cbt", "start": "2026-09-01", "end": "2026-09-07", "consent": True},
    )
    assert response.status_code == 201, response.text
    # обычная запись в анализ ушла — значит, приватная исключена фильтром, а не данными нет
    assert any("обычная запись про сон" in sent for sent in provider.sent)
    assert env["ct"] not in response.text
    assert all(env["ct"] not in sent for sent in provider.sent)
    assert "работа" not in " ".join(provider.sent)


@pytest.mark.parametrize(
    "bad",
    [
        {"v": 2},
        {"kdf": "MD5"},
        {"iter": 1000},
        {"iter": True},
        {"salt": "AAAA"},
        {"salt": 12345},
        {"iv": b64(8)},
        {"ct": "не-base64!"},
        {"ct": b64(4)},
    ],
)
def test_malformed_envelope_rejected(api: TestClient, bad: dict[str, Any]) -> None:
    response = api.post("/api/entries", json={"protection": "private", "cipher": envelope(**bad)})
    assert response.status_code == 422
    assert api.get("/api/entries").json() == []


def test_private_requires_cipher_and_plain_rejects_it(api: TestClient) -> None:
    assert api.post("/api/entries", json={"protection": "private"}).status_code == 422
    plain = api.post("/api/entries", json={"text": "a", "cipher": envelope()})
    assert plain.status_code == 422
    assert api.get("/api/entries").json() == []
