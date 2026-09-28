"""Hardening (kognis-yaj): ограничение попыток входа, заголовки безопасности, приватность логов."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

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
    assert "слишком много попыток" in blocked.json()["detail"]
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
