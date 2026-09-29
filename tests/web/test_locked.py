"""Записи «под замком»: приёмочные тесты kognis-83s (AC1–AC3) и границы режима."""

import base64
import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

from kognis.web import create_app

VALID_PW = "correct horse"
LOCK_PW = "замок-12345"
PRIVATE_TEXT = "Секретная мысль про начальника"
KEY_A = base64.b64encode(b"A" * 32).decode()
KEY_B = base64.b64encode(b"B" * 32).decode()
DAY = dt.date(2026, 9, 1)
NOON = dt.datetime(2026, 9, 1, 12, tzinfo=dt.UTC)  # 2026-09-01 и в МСК


def make_client(
    engine: Engine, key: str | None = KEY_A, email: str = "ann@example.com"
) -> TestClient:
    client = TestClient(create_app(engine, clock=lambda: NOON, data_key=key))
    response = client.post("/api/auth/register", json={"email": email, "password": VALID_PW})
    assert response.status_code in (201, 409)
    if response.status_code == 409:
        assert (
            client.post("/api/auth/login", json={"email": email, "password": VALID_PW}).status_code
            == 200
        )
    return client


@pytest.fixture
def api(engine: Engine) -> TestClient:
    return make_client(engine)


def create_locked(client: TestClient, text: str = PRIVATE_TEXT) -> dict[str, Any]:
    response = client.post(
        "/api/entries",
        json={"text": text, "tags": ["работа"], "protection": "locked", "lock_password": LOCK_PW},
    )
    assert response.status_code == 201, response.text
    return response.json()


def raw_rows(engine: Engine) -> str:
    """Все байты и строки таблицы entries — как их видит тот, кто читает БД напрямую."""
    with engine.connect() as conn:
        rows = conn.execute(sql("SELECT * FROM entries")).all()
    return repr(rows)


@pytest.mark.acceptance("kognis-83s", "AC1")
def test_locked_text_stored_only_encrypted(api: TestClient, engine: Engine) -> None:
    created = create_locked(api)
    assert created["protection"] == "locked"
    assert created["text"] == ""
    dump = raw_rows(engine)
    assert PRIVATE_TEXT not in dump
    assert PRIVATE_TEXT.encode() not in dump.encode("unicode_escape")
    with engine.connect() as conn:
        row = conn.execute(sql("SELECT text, lock_cipher, lock_hash FROM entries")).one()
    assert row.text == ""
    assert row.lock_cipher
    assert PRIVATE_TEXT.encode() not in bytes(row.lock_cipher)
    assert row.lock_hash.startswith("$argon2id$")
    # в списке и по id — заглушка без текста
    assert [e["text"] for e in api.get("/api/entries").json()] == [""]
    assert api.get(f"/api/entries/{created['id']}").json()["text"] == ""


@pytest.mark.acceptance("kognis-83s", "AC2")
def test_wrong_password_never_reveals_text(api: TestClient) -> None:
    entry_id = create_locked(api)["id"]
    bad = api.post(f"/api/entries/{entry_id}/open", json={"password": "неверный-пароль"})
    assert bad.status_code == 403
    assert "пароль" in bad.json()["detail"]
    assert PRIVATE_TEXT not in bad.text
    good = api.post(f"/api/entries/{entry_id}/open", json={"password": LOCK_PW})
    assert good.status_code == 200
    assert good.json()["text"] == PRIVATE_TEXT
    # после открытия запись остаётся закрытой
    assert api.get(f"/api/entries/{entry_id}").json()["text"] == ""


@pytest.mark.acceptance("kognis-83s", "AC3")
def test_changed_data_key_makes_entry_unreadable_but_app_lives(
    api: TestClient, engine: Engine
) -> None:
    entry_id = create_locked(api)["id"]
    plain = api.post("/api/entries", json={"text": "обычная"}).json()
    other = make_client(engine, key=KEY_B)
    response = other.post(f"/api/entries/{entry_id}/open", json={"password": LOCK_PW})
    assert response.status_code == 409
    assert "ключ данных" in response.json()["detail"]
    assert PRIVATE_TEXT not in response.text
    # приложение живо: список, обычные записи и новые замки со своим ключом работают
    listed = other.get("/api/entries").json()
    assert {e["id"] for e in listed} == {entry_id, plain["id"]}
    assert other.get(f"/api/entries/{plain['id']}").json()["text"] == "обычная"
    create_locked(other, "новая")
    # ключ не задан совсем — тоже понятная ошибка, а не 500
    keyless = make_client(engine, key=None)
    lost = keyless.post(f"/api/entries/{entry_id}/open", json={"password": LOCK_PW})
    assert lost.status_code == 503
    assert (
        keyless.post(
            "/api/entries",
            json={"text": "x", "protection": "locked", "lock_password": LOCK_PW},
        ).status_code
        == 503
    )


def test_lock_and_unlock_existing_entry(api: TestClient, engine: Engine) -> None:
    entry_id = api.post("/api/entries", json={"text": PRIVATE_TEXT}).json()["id"]
    locked = api.post(f"/api/entries/{entry_id}/lock", json={"password": LOCK_PW})
    assert locked.status_code == 200
    assert locked.json()["protection"] == "locked"
    assert PRIVATE_TEXT not in raw_rows(engine)
    wrong = api.post(f"/api/entries/{entry_id}/unlock", json={"password": "неверный-пароль"})
    assert wrong.status_code == 403
    assert api.post(f"/api/entries/{entry_id}/unlock", json={"password": LOCK_PW}).json() == {
        **api.get(f"/api/entries/{entry_id}").json(),
    }
    assert api.get(f"/api/entries/{entry_id}").json()["text"] == PRIVATE_TEXT


def test_short_or_missing_lock_password_rejected(api: TestClient) -> None:
    short = api.post(
        "/api/entries", json={"text": "a", "protection": "locked", "lock_password": "123"}
    )
    assert short.status_code == 422
    missing = api.post("/api/entries", json={"text": "a", "protection": "locked"})
    assert missing.status_code == 422
    assert api.get("/api/entries").json() == []


def test_other_user_cannot_open(api: TestClient, engine: Engine) -> None:
    entry_id = create_locked(api)["id"]
    eve = make_client(engine, email="eve@example.com")
    response = eve.post(f"/api/entries/{entry_id}/open", json={"password": LOCK_PW})
    assert response.status_code == 404


def test_locked_entries_excluded_from_analysis_payload(api: TestClient) -> None:
    create_locked(api)
    response = api.post(
        "/api/analyses",
        json={
            "direction": "cbt",
            "start": "2026-09-01",
            "end": "2026-09-07",
            "consent": True,
        },
    )
    assert PRIVATE_TEXT not in response.text


def test_wrong_password_attempts_are_limited(api: TestClient) -> None:
    entry_id = create_locked(api)["id"]
    url = f"/api/entries/{entry_id}/open"
    for _ in range(5):
        assert api.post(url, json={"password": "неверный-пароль"}).status_code == 403
    blocked = api.post(url, json={"password": LOCK_PW})
    assert blocked.status_code == 429
    assert PRIVATE_TEXT not in blocked.text


def test_open_response_is_not_cacheable(api: TestClient) -> None:
    entry_id = create_locked(api)["id"]
    response = api.post(f"/api/entries/{entry_id}/open", json={"password": LOCK_PW})
    assert response.headers["cache-control"] == "no-store"


def test_lock_endpoints_edge_cases(api: TestClient) -> None:
    plain_id = api.post("/api/entries", json={"text": "обычная"}).json()["id"]
    assert api.post(f"/api/entries/{plain_id}/lock", json={"password": "123"}).status_code == 422
    opened = api.post(f"/api/entries/{plain_id}/open", json={"password": LOCK_PW})
    assert opened.json()["text"] == "обычная"
    unlocked = api.post(f"/api/entries/{plain_id}/unlock", json={"password": LOCK_PW})
    assert unlocked.status_code == 200
    locked_id = create_locked(api)["id"]
    # повторное закрытие ничего не меняет
    again = api.post(f"/api/entries/{locked_id}/lock", json={"password": "другой-пароль"})
    assert again.json()["protection"] == "locked"
    assert api.post(f"/api/entries/{locked_id}/open", json={"password": LOCK_PW}).status_code == 200
    for action in ("open", "lock", "unlock"):
        missing = api.post(f"/api/entries/9999/{action}", json={"password": LOCK_PW})
        assert missing.status_code == 404


@pytest.mark.parametrize("bad_key", ["не-base64!", base64.b64encode(b"short").decode()])
def test_invalid_data_key_is_clear_error(engine: Engine, bad_key: str) -> None:
    client = make_client(engine, key=bad_key)
    response = client.post(
        "/api/entries", json={"text": "x", "protection": "locked", "lock_password": LOCK_PW}
    )
    assert response.status_code == 503
    assert "ключ данных" in response.json()["detail"]
