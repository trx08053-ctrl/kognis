"""Эксплуатация: kognis-e7s — /health проверяет БД, документация API только в dev, RUNBOOK."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from kognis.web import create_app

RUNBOOK = Path(__file__).resolve().parents[2] / "docs" / "RUNBOOK.md"
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@pytest.mark.acceptance("kognis-e7s", "AC1")
def test_health_ok_with_database(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.acceptance("kognis-e7s", "AC1")
def test_health_503_without_details_when_database_is_down(tmp_path: Path) -> None:
    broken = create_engine(f"sqlite:///{tmp_path / 'missing' / 'db.sqlite'}")  # каталога нет
    response = TestClient(create_app(broken)).get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "missing" not in response.text


@pytest.mark.acceptance("kognis-e7s", "AC2")
def test_api_docs_available_in_dev(client: TestClient) -> None:
    for path in DOC_PATHS:
        assert client.get(path).status_code == 200, path


@pytest.mark.acceptance("kognis-e7s", "AC2")
def test_api_docs_hidden_outside_dev(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOGNIS_ENV")
    app = create_app(engine)
    client = TestClient(app)
    for path in DOC_PATHS:
        assert client.get(path).status_code == 404, path
    assert "paths" in app.openapi()  # генератор типов фронтенда берёт схему напрямую


@pytest.mark.source
@pytest.mark.acceptance("kognis-e7s", "AC3")
def test_runbook_uses_just_backup_and_restore_not_manual_commands() -> None:
    text = RUNBOOK.read_text()
    assert not re.search(r"docker compose[^\n]*(pg_dump|pg_restore)", text)
    assert "just backup" in text
    assert "just restore" in text
