"""Коды ошибок вместо фраз: приёмочные тесты kognis-b7x (AC1, AC2); AC3, AC4 — test_locale.py."""

import ast
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app
from kognis.web._errors import http_error

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
CYRILLIC = re.compile("[А-Яа-яЁё]")
PW = "correct horse"

# (метод, путь, тело, нужен вход, статус, код) — известные ошибки для человека
CASES: list[tuple[str, str, dict[str, Any] | None, bool, int, str]] = [
    ("GET", "/api/me", None, False, 401, "auth.required"),
    ("POST", "/api/auth/register", {}, False, 422, "request.validation"),
    ("GET", "/api/nothing-here", None, False, 404, "http.not_found"),
    (
        "POST",
        "/api/auth/login",
        {"email": "x@example.com", "password": PW},
        False,
        401,
        "user.credentials_invalid",
    ),
    (
        "POST",
        "/api/auth/register",
        {"email": "bad", "password": PW},
        False,
        422,
        "user.email_invalid",
    ),
    (
        "POST",
        "/api/auth/register",
        {"email": "b@example.com", "password": "short"},
        False,
        422,
        "user.password_short",
    ),
    (
        "POST",
        "/api/auth/register",
        {"email": "ann@example.com", "password": PW},
        True,
        409,
        "user.email_taken",
    ),
    ("PUT", "/api/me/settings", {}, True, 422, "settings.empty"),
    ("PUT", "/api/me/settings", {"timezone": "Mars/Base"}, True, 422, "user.timezone_unknown"),
    ("POST", "/api/entries", {"text": "   "}, True, 422, "diary.text_empty"),
    (
        "POST",
        "/api/entries",
        {"text": "x", "protection": "locked"},
        True,
        422,
        "lock.password_required",
    ),
    (
        "POST",
        "/api/entries",
        {"text": "x", "protection": "private"},
        True,
        422,
        "diary.private_cipher_only",
    ),
    (
        "PUT",
        "/api/day-reviews/2026-09-01",
        {"wellbeing": 0, "mood": 5, "reflection": ""},
        True,
        422,
        "diary.wellbeing_range",
    ),
    (
        "POST",
        "/api/analyses",
        {"direction": "cbt", "start": "2026-09-01", "end": "2026-09-02"},
        True,
        403,
        "analysis.consent_required",
    ),
    ("POST", "/api/quests/999999/steps/0/done", {}, True, 404, "gameplay.quest_not_found"),
]


def is_coded(detail: Any) -> bool:
    if not isinstance(detail, dict):
        return False
    body = cast("dict[str, Any]", detail)
    return isinstance(body.get("code"), str) and isinstance(body.get("params"), dict)


@pytest.mark.acceptance("kognis-b7x", "AC1")
@pytest.mark.parametrize("case", CASES, ids=[f"{c[0]} {c[1]} {c[5]}" for c in CASES])
def test_known_errors_carry_code_not_phrase(
    engine: Engine, case: tuple[str, str, dict[str, Any] | None, bool, int, str]
) -> None:
    method, path, body, authed, status, code = case
    client = TestClient(create_app(engine))
    if authed:
        client.post("/api/auth/register", json={"email": "ann@example.com", "password": PW})
    response = client.request(method, path, json=body)
    assert response.status_code == status
    detail = response.json()["detail"]
    assert is_coded(detail)
    assert detail["code"] == code
    assert not CYRILLIC.search(response.text)


@pytest.mark.acceptance("kognis-b7x", "AC1")
def test_oversized_body_and_server_error_are_coded(engine: Engine) -> None:
    client = TestClient(create_app(engine))
    big = client.post(
        "/api/auth/login",
        content=b"{" + b" " * (600 * 1024) + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert big.status_code == 413
    assert big.json()["detail"]["code"] == "http.body_too_large"
    wrong_type = client.post(
        "/api/auth/login", content=b"x", headers={"Content-Type": "text/plain"}
    )
    assert wrong_type.status_code == 415
    assert wrong_type.json()["detail"]["code"] == "http.json_required"


def test_foreign_exception_never_leaks_its_text() -> None:
    """Чужое ValueError (не для показа) даёт общий код, а не своё сообщение.

    Напрямую к приватному помощнику: обычный ввод такой путь не проходит (домен бросает
    только ошибки с кодом), а гарантия «текст исключения наружу не идёт» нужна.
    """
    error = http_error(422, ValueError("secret detail"))
    assert error.detail == {"code": "request.invalid", "params": {}}


@pytest.mark.source
@pytest.mark.acceptance("kognis-b7x", "AC1")
def test_no_russian_phrases_in_raised_exceptions() -> None:
    """В src/ исключения не несут русский текст: только коды (docs/I18N.md, правило 2)."""
    offenders = [
        f"{path.relative_to(ROOT)}:{node.lineno}"
        for path in SRC.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Raise) and node.exc is not None
        for part in ast.walk(node.exc)
        if isinstance(part, ast.Constant)
        and isinstance(part.value, str)
        and CYRILLIC.search(part.value)
    ]
    assert offenders == []


@pytest.mark.source
@pytest.mark.acceptance("kognis-b7x", "AC2")
def test_frontend_shows_text_by_code_and_generic_text_for_unknown() -> None:
    pnpm = shutil.which("pnpm")
    assert pnpm, "нет pnpm"
    result = subprocess.run(
        [
            pnpm,
            "--dir",
            "frontend",
            "exec",
            "vitest",
            "run",
            "--coverage.enabled=false",
            "src/errors.test.ts",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.source
@pytest.mark.acceptance("kognis-b7x", "AC2")
def test_every_server_code_has_dictionary_text() -> None:
    """Каждый код, который сервер может отдать, есть в словаре интерфейса (`error.<код>`)."""
    dictionary = (ROOT / "frontend" / "src" / "i18n" / "ru.ts").read_text()
    code = re.compile(r'"((?:[a-z_]+)\.(?:[a-z_]+))"')
    used: set[str] = set()
    for path in SRC.rglob("*.py"):
        used |= {
            m
            for m in code.findall(path.read_text())
            if m.split(".")[0]
            in {
                "auth",
                "http",
                "server",
                "settings",
                "access",
                "user",
                "lock",
                "data_key",
                "entry",
                "diary",
                "analysis",
                "gameplay",
                "ai",
                "request",
            }
        }
    used.discard("http.request")  # тип сообщения ASGI в _limits.py, не код ошибки
    missing = sorted(c for c in used if f'"error.{c}"' not in dictionary)
    assert missing == []
