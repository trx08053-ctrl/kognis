"""Hardening (kognis-yaj): ограничение попыток входа, заголовки безопасности, приватность логов."""

import base64
import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from kognis.db import transaction
from kognis.users import LoginBlockedError, UserService
from kognis.users._infra import utcnow
from kognis.web import create_app

VALID_PW = "correct horse"
WRONG_PW = "definitely wrong"


def login(client: TestClient, email: str, password: str) -> int:
    return client.post("/api/auth/login", json={"email": email, "password": password}).status_code


@pytest.fixture
def registered(client: TestClient) -> TestClient:
    client.post("/api/auth/register", json={"email": "ann@example.com", "password": VALID_PW})
    client.post("/api/auth/logout", json={})
    return client


@pytest.mark.acceptance("kognis-yaj", "AC1")
def test_five_failures_block_login_with_clear_message(registered: TestClient) -> None:
    for _ in range(5):
        assert login(registered, "ann@example.com", WRONG_PW) == 401
    blocked = registered.post(
        "/api/auth/login", json={"email": "ann@example.com", "password": VALID_PW}
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "user.login_blocked"
    assert 1 <= int(blocked.headers["retry-after"]) <= 15 * 60
    # блокировка действует и на другой регистр записи email
    assert login(registered, " ANN@example.com ", VALID_PW) == 429


def test_four_failures_do_not_block_and_success_resets(registered: TestClient) -> None:
    for _ in range(4):
        assert login(registered, "ann@example.com", WRONG_PW) == 401
    assert login(registered, "ann@example.com", VALID_PW) == 200
    for _ in range(4):
        assert login(registered, "ann@example.com", WRONG_PW) == 401
    assert login(registered, "ann@example.com", VALID_PW) == 200


def test_block_is_per_email_but_ip_limit_covers_many_emails(registered: TestClient) -> None:
    for _ in range(5):
        login(registered, "ann@example.com", WRONG_PW)
    assert login(registered, "bob@example.com", WRONG_PW) == 401  # другой email — не заблокирован
    for i in range(20):  # перебор разных email с одного IP
        login(registered, f"user{i}@example.com", WRONG_PW)
    assert login(registered, "carol@example.com", VALID_PW) == 429


def test_block_survives_restart_and_expires_after_window(
    registered: TestClient, engine: Engine
) -> None:
    for _ in range(5):
        login(registered, "ann@example.com", WRONG_PW)
    restarted = TestClient(create_app(engine))  # счётчик в БД, а не в памяти процесса
    assert login(restarted, "ann@example.com", VALID_PW) == 429

    with transaction(engine) as session:
        service = UserService(session)
        with pytest.raises(LoginBlockedError):
            service.ensure_login_allowed("ann@example.com", "testclient")
        later = utcnow() + timedelta(minutes=16)
        service.ensure_login_allowed("ann@example.com", "testclient", now=later)
        service.record_login_failure("bob@example.com", "testclient", now=later)  # чистит старое
    assert login(restarted, "ann@example.com", VALID_PW) == 200


def test_malformed_email_attempts_are_counted_too(client: TestClient) -> None:
    for _ in range(5):
        assert login(client, "not-an-email", WRONG_PW) == 401
    assert login(client, "not-an-email", WRONG_PW) == 429


def test_service_raises_blocked_error(engine: Engine) -> None:
    with transaction(engine) as session:
        service = UserService(session)
        for _ in range(5):
            service.record_login_failure("ann@example.com", "1.2.3.4")
        with pytest.raises(LoginBlockedError) as info:
            service.ensure_login_allowed("ann@example.com", "9.9.9.9")
    assert info.value.retry_after > 0


ENTRY_TEXT = "Тайная мысль про начальника"
LOCK_PW = "замок-пароль-123"


@pytest.mark.acceptance("kognis-yaj", "AC3")
def test_entry_texts_never_reach_logs(
    engine: Engine, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KOGNIS_DATA_KEY", base64.b64encode(b"K" * 32).decode())
    caplog.set_level(logging.DEBUG)  # всё, на любом уровне и от любого логгера
    api = TestClient(create_app(engine), raise_server_exceptions=False)
    api.post("/api/auth/register", json={"email": "ann@example.com", "password": VALID_PW})
    body = {"text": ENTRY_TEXT, "tags": ["тег-тайна"], "emotions": ["эмоция-тайна"]}
    assert api.post("/api/entries", json=body).status_code == 201
    locked = {**body, "protection": "locked", "lock_password": LOCK_PW}
    assert api.post("/api/entries", json=locked).status_code == 201
    api.post("/api/entries", json={"text": ENTRY_TEXT, "protection": "private", "cipher": {"v": 1}})
    api.post("/api/day-reviews", json={"wellbeing": 5, "mood": 5, "reflection": ENTRY_TEXT})
    api.post("/api/auth/login", json={"email": "ann@example.com", "password": LOCK_PW})
    # сбой хранилища: необработанная ошибка БД не должна тащить в лог параметры запроса с текстом
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE entries")
    assert api.post("/api/entries", json=body).status_code == 500
    logged = caplog.text + "".join(str(r.exc_info[1]) for r in caplog.records if r.exc_info)
    for hidden in (ENTRY_TEXT, "тег-тайна", "эмоция-тайна", LOCK_PW):
        assert hidden not in logged


def test_database_errors_hide_query_parameters(engine: Engine) -> None:
    with pytest.raises(SQLAlchemyError) as info, engine.begin() as conn:
        conn.execute(text("INSERT INTO no_such_table (body) VALUES (:body)"), {"body": ENTRY_TEXT})
    assert ENTRY_TEXT not in str(info.value)


@pytest.mark.acceptance("kognis-yaj", "AC2")
def test_security_headers_on_pages_assets_and_api(client: TestClient) -> None:
    for path in ("/", "/health", "/api/me", "/assets/missing.js"):
        headers = client.get(path).headers
        csp = headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "'unsafe-inline'" not in csp
        assert "'unsafe-eval'" not in csp
        assert headers["x-frame-options"] == "DENY"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/me").headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in client.get("/health").headers  # dev по http


def test_hsts_when_not_dev(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOGNIS_ENV")
    headers = TestClient(create_app(engine)).get("/health").headers
    assert "max-age=" in headers["strict-transport-security"]
