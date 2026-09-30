"""Язык пользователя в профиле: приёмочные тесты kognis-b7x (AC3)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from kognis.db import make_engine
from kognis.web import create_app

ROOT = Path(__file__).resolve().parents[2]
PW = "correct horse"


def register(client: TestClient, accept_language: str | None = None) -> dict[str, object]:
    headers = {"Accept-Language": accept_language} if accept_language else {}
    response = client.post(
        "/api/auth/register", json={"email": "ann@example.com", "password": PW}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def two_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Второй язык включён только на время теста: в проекте пока единственный язык — ru."""
    monkeypatch.setattr("kognis.users._domain.SUPPORTED_LOCALES", ("ru", "en"))


@pytest.mark.migration
@pytest.mark.acceptance("kognis-b7x", "AC3")
def test_migration_adds_locale_up_and_removes_it_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "0013")  # схема прошлого релиза
    engine = make_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, created_at, advanced, timezone) "
                "VALUES ('old@example.com', 'x', '2026-01-01 00:00:00', 0, 'Europe/Moscow')"
            )
        )

    command.upgrade(config, "0014")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT locale FROM users")).scalar_one() == "ru"

    command.downgrade(config, "0013")
    with engine.connect() as conn:
        columns = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        assert "locale" not in columns
        assert conn.execute(text("SELECT email FROM users")).scalar_one() == "old@example.com"


@pytest.mark.acceptance("kognis-b7x", "AC3")
def test_put_rejects_unsupported_locale_with_code(client: TestClient) -> None:
    register(client)
    for bad in ["xx", "RU", "ru-RU", "", "a" * 17, "ru; drop table users"]:
        response = client.put("/api/me/settings", json={"locale": bad})
        assert response.status_code == 422, bad
    rejected = client.put("/api/me/settings", json={"locale": "xx"})
    assert rejected.json()["detail"] == {"code": "user.locale_unsupported", "params": {}}
    assert client.get("/api/me").json()["locale"] == "ru"


@pytest.mark.acceptance("kognis-b7x", "AC3")
def test_put_saves_supported_locale_and_me_returns_it(
    client: TestClient, two_languages: None
) -> None:
    register(client)
    saved = client.put("/api/me/settings", json={"locale": "en"})
    assert saved.status_code == 200
    assert saved.json()["locale"] == "en"
    assert client.get("/api/me").json()["locale"] == "en"


@pytest.mark.acceptance("kognis-b7x", "AC3")
def test_registration_takes_language_from_accept_language(
    client: TestClient, two_languages: None
) -> None:
    assert register(client, "fr-CH, en-US;q=0.9, ru;q=0.5")["locale"] == "en"


@pytest.mark.acceptance("kognis-b7x", "AC3")
@pytest.mark.parametrize(
    "header",
    [None, "", "de, fr;q=0.9", "*", "en;q=abc", ";;;,,,", "x" * 5000, "en;q=0"],
)
def test_registration_falls_back_to_default_language(
    client: TestClient, two_languages: None, header: str | None
) -> None:
    assert register(client, header)["locale"] == "ru"


@pytest.mark.acceptance("kognis-b7x", "AC3")
def test_empty_locale_in_old_rows_reads_as_default(engine: Engine) -> None:
    client = TestClient(create_app(engine))
    register(client)
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET locale = NULL"))
    assert client.get("/api/me").json()["locale"] == "ru"
