"""Скрипт засева для замеров производительности: идёт через API и даёт cookie для `just perf`."""

import datetime as dt
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_perf.py"

# скрипт не копируется в mutants/ — тест читает его из репозитория
pytestmark = pytest.mark.source


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_perf", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClientAdapter:
    """Тот же интерфейс, что у `Client` скрипта, но поверх TestClient (без сети)."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def call(self, method: str, path: str, body: dict[str, object] | None = None) -> int:
        return self.client.request(method, path, json=body).status_code

    def cookie(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.client.cookies.items())


def test_seed_creates_pages_worth_of_data(client: TestClient) -> None:
    seed_perf = load()
    api = ClientAdapter(client)
    seed_perf.sign_in(api, "perf@example.com", "correct horse")
    assert seed_perf.sign_in(api, "perf@example.com", "correct horse") is None  # повторный вход
    entries, reviews = seed_perf.seed(api, days=12, per_day=3, today=dt.date(2026, 9, 29))
    assert (entries, reviews) == (36, 12)
    assert api.cookie().startswith("kognis_session=")
    assert len(client.get("/api/entries", params={"limit": 100}).json()) == 36
    assert len(client.get("/api/day-reviews", params={"limit": 100}).json()) == 12


def test_seed_refuses_wrong_password(client: TestClient) -> None:
    seed_perf = load()
    api = ClientAdapter(client)
    seed_perf.sign_in(api, "perf@example.com", "correct horse")
    other = ClientAdapter(TestClient(client.app))
    with pytest.raises(SystemExit):
        seed_perf.sign_in(other, "perf@example.com", "wrong password")
