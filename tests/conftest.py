"""Общие фикстуры веб-приложения: БД со схемой из миграций, HTTP-клиент, живой сервер для e2e."""

import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from testcontainers.postgres import PostgresContainer

from kognis.db import make_engine
from kognis.web import create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def dev_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тесты ходят по http: cookie без Secure. По умолчанию (без KOGNIS_ENV=dev) Secure включён."""
    monkeypatch.setenv("KOGNIS_ENV", "dev")


@pytest.fixture
def crisis_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Кризисный детектор включён явно (по умолчанию он выключен — kognis-xci)."""
    monkeypatch.setenv("KOGNIS_CRISIS_DETECTOR", "on")


@pytest.fixture(autouse=True)
def crisis_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тесты не зависят от окружения разработчика: без явного `crisis_on` детектор выключен."""
    monkeypatch.delenv("KOGNIS_CRISIS_DETECTOR", raising=False)


def migrate(url: str, monkeypatch: pytest.MonkeyPatch) -> Engine:
    """Схема — только из миграций Alembic (как в продакшене)."""
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    return make_engine(url)


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    return migrate(f"sqlite:///{tmp_path / 'test.db'}", monkeypatch)


@pytest.fixture
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(engine))


@pytest.fixture
def live_server(engine: Engine) -> Iterator[str]:
    """Приложение на свободном порту в фоне — для e2e в браузере."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(engine), port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def docker_available() -> bool:
    docker = shutil.which("docker")
    if docker is None:
        return False
    return subprocess.run([docker, "info"], capture_output=True, check=False).returncode == 0


@pytest.fixture
def pg_url() -> Iterator[str]:
    """PostgreSQL в контейнере. Без Docker (например, в песочнице агента) — тест пропускается явно;
    в CI Docker есть, и эти тесты выполняются всегда."""
    if not docker_available() or os.environ.get("NO_DOCKER_TESTS"):
        pytest.skip("нет Docker: PostgreSQL — в CI")  # justified: harness-web песочница
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture
def pg_engine(pg_url: str, monkeypatch: pytest.MonkeyPatch) -> Engine:
    return migrate(pg_url, monkeypatch)
