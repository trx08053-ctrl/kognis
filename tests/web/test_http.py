from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_api_create_and_list(client: TestClient) -> None:
    created = client.post("/api/users", json={"name": " Ann "})
    assert created.status_code == 201
    assert created.json()["name"] == "Ann"
    assert [u["name"] for u in client.get("/api/users").json()] == ["Ann"]


def test_api_rejects_blank_name(client: TestClient) -> None:
    response = client.post("/api/users", json={"name": "  "})
    assert response.status_code == 422
    assert "пуст" in response.json()["detail"]


def test_serves_built_frontend(engine: Engine, tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    client = TestClient(create_app(engine, frontend_dist=tmp_path))
    assert "id=root" in client.get("/").text
    assert client.get("/assets/app.js").status_code == 200


def test_unbuilt_frontend_is_explicit(engine: Engine, tmp_path: Path) -> None:
    response = TestClient(create_app(engine, frontend_dist=tmp_path)).get("/")
    assert response.status_code == 503
    assert "pnpm" in response.text
