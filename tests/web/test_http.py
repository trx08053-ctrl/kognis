from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app

VALID_PW = "correct horse"


def signup(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/register", json={"email": email, "password": VALID_PW})
    assert response.status_code == 201


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_register_sets_httponly_cookie_and_me_works(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": " Ann@Example.com ", "password": VALID_PW}
    )
    cookie = response.headers["set-cookie"].lower()
    assert "kognis_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert client.get("/api/me").json()["email"] == "ann@example.com"


def test_me_requires_login(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/entries").status_code == 401
    assert client.post("/api/entries", json={"text": "x"}).status_code == 401


def test_login_logout(client: TestClient) -> None:
    signup(client, "ann@example.com")
    client.post("/api/auth/logout", json={})
    assert client.get("/api/me").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "ann@example.com", "password": "nope nope"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": "ann@example.com", "password": VALID_PW})
    assert ok.status_code == 200
    assert client.get("/api/me").status_code == 200


def test_register_validation_and_duplicates(client: TestClient) -> None:
    assert (
        client.post("/api/auth/register", json={"email": "x", "password": VALID_PW}).status_code
        == 422
    )
    assert (
        client.post("/api/auth/register", json={"email": "a@b.co", "password": "1"}).status_code
        == 422
    )
    signup(client, "ann@example.com")
    dup = client.post("/api/auth/register", json={"email": "ANN@example.com", "password": VALID_PW})
    assert dup.status_code == 409


def test_mutations_require_json_content_type(client: TestClient) -> None:
    response = client.post("/api/auth/logout", content=b"", headers={"content-type": "text/plain"})
    assert response.status_code == 415


def test_entry_validation(client: TestClient) -> None:
    signup(client, "ann@example.com")
    response = client.post("/api/entries", json={"text": "   "})
    assert response.status_code == 422
    assert "пуст" in response.json()["detail"]


def test_unknown_api_path_is_404_not_spa(client: TestClient) -> None:
    assert client.get("/api/nope").status_code == 404


def test_serves_built_frontend_for_spa_routes(engine: Engine, tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    client = TestClient(create_app(engine, frontend_dist=tmp_path))
    assert "id=root" in client.get("/").text
    assert "id=root" in client.get("/login").text
    assert client.get("/assets/app.js").status_code == 200


def test_unbuilt_frontend_is_explicit(engine: Engine, tmp_path: Path) -> None:
    response = TestClient(create_app(engine, frontend_dist=tmp_path)).get("/")
    assert response.status_code == 503
    assert "pnpm" in response.text


@pytest.mark.acceptance("kognis-b8z", "AC2")
@pytest.mark.e2e
def test_u1_over_http_survives_restart_and_isolates_users(engine: Engine) -> None:
    """U1 по HTTP: регистрация → запись → «перезапуск» (новое приложение) → вход → запись на месте;
    второй пользователь не видит чужую запись ни в списке, ни по id (R1)."""
    first = TestClient(create_app(engine))
    signup(first, "ann@example.com")
    created = first.post(
        "/api/entries",
        json={
            "text": "Сегодня было тревожно",
            "tags": ["работа"],
            "emotions": ["тревога"],
            "date": "2026-09-01",
        },
    )
    assert created.status_code == 201
    entry_id = created.json()["id"]

    restarted = TestClient(create_app(engine))  # новое приложение, новое соединение, нет cookie
    assert restarted.get("/api/entries").status_code == 401
    login = restarted.post(
        "/api/auth/login", json={"email": "ann@example.com", "password": VALID_PW}
    )
    assert login.status_code == 200
    entries = restarted.get("/api/entries").json()
    assert [(e["text"], e["tags"], e["emotions"], e["date"]) for e in entries] == [
        ("Сегодня было тревожно", ["работа"], ["тревога"], "2026-09-01")
    ]

    other = TestClient(create_app(engine))
    signup(other, "bob@example.com")
    assert other.get("/api/entries").json() == []
    assert other.get(f"/api/entries/{entry_id}").status_code == 404
    assert restarted.get(f"/api/entries/{entry_id}").status_code == 200
