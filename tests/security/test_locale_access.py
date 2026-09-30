"""Язык профиля: доступ только к своему профилю (kognis-b7x, AC4)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

PW = "correct horse"


@pytest.fixture(autouse=True)
def two_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kognis.users._domain.SUPPORTED_LOCALES", ("ru", "en"))


def signed_up(engine: Engine, email: str, language: str) -> TestClient:
    client = TestClient(create_app(engine))
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PW},
        headers={"Accept-Language": language},
    )
    assert response.status_code == 201
    return client


@pytest.mark.security("access", "PUT /api/me/settings")
@pytest.mark.acceptance("kognis-b7x", "AC4")
def test_locale_can_only_be_changed_by_the_owner_of_the_profile(engine: Engine) -> None:
    ann = signed_up(engine, "ann@example.com", "ru")
    eve = signed_up(engine, "eve@example.com", "ru")
    assert eve.put("/api/me/settings", json={"locale": "en"}).status_code == 200
    assert eve.get("/api/me").json()["locale"] == "en"
    assert ann.get("/api/me").json()["locale"] == "ru"


@pytest.mark.security("access", "PUT /api/me/settings")
@pytest.mark.acceptance("kognis-b7x", "AC4")
def test_anonymous_cannot_read_or_change_locale(engine: Engine) -> None:
    signed_up(engine, "ann@example.com", "en")
    anonymous = TestClient(create_app(engine))
    assert anonymous.get("/api/me").status_code == 401
    assert anonymous.put("/api/me/settings", json={"locale": "en"}).status_code == 401


@pytest.mark.security("access", "PUT /api/me/settings")
@pytest.mark.acceptance("kognis-b7x", "AC4")
def test_settings_ignore_attempts_to_target_another_user(engine: Engine) -> None:
    ann = signed_up(engine, "ann@example.com", "ru")
    eve = signed_up(engine, "eve@example.com", "ru")
    response = eve.put("/api/me/settings", json={"locale": "en", "id": 1, "user_id": 1})
    assert response.status_code == 200
    assert ann.get("/api/me").json()["locale"] == "ru"
    assert response.json()["email"] == "eve@example.com"
