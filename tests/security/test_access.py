"""Контроль доступа (OWASP A01) — проверки harness, файл защищён.

1. Каждый HTTP-маршрут либо явно публичный (security/public-routes.txt, защищённый файл —
   решение человека), либо без сессии отвечает 401/403: новый endpoint не останется открытым.
2. Для каждого закрытого маршрута с идентификатором в пути ({…}) есть тест на доступ к чужому
   ресурсу (IDOR): `@pytest.mark.security("idor", "GET /api/items/{item_id}")` — пользователь B
   получает 404 на объект пользователя A (не 403: не раскрывать существование). docs/SECURITY.md.
"""

import re
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi import routing as fastapi_routing
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_FILE = ROOT / "security" / "public-routes.txt"
IDOR_MARK = re.compile(r"""@pytest\.mark\.security\(\s*["']idor["']\s*,\s*["']([^"']+)["']""")
DENIED = {401, 403}


def routes(client: TestClient) -> list[str]:
    """Все маршруты приложения с учётом include_router (и скрытые из OpenAPI): «METHOD /path»."""
    app_routes = cast("FastAPI", client.app).routes
    iterate = getattr(
        fastapi_routing, "iter_route_contexts", None
    )  # FastAPI ≥ 0.140: вложенные роутеры
    contexts = (
        [(c.original_route, c.path, c.methods) for c in iterate(app_routes)]
        if iterate
        else [(r, getattr(r, "path", None), getattr(r, "methods", None)) for r in app_routes]
    )
    found = {
        f"{method} {path}"
        for route, path, methods in contexts
        if isinstance(route, APIRoute) and path
        for method in methods or set[str]()
        if method not in {"HEAD", "OPTIONS"}
    }
    return sorted(found)


def public_routes() -> set[str]:
    lines = PUBLIC_FILE.read_text().splitlines() if PUBLIC_FILE.exists() else []
    return {" ".join(ln.split("#", 1)[0].split()) for ln in lines if ln.split("#", 1)[0].strip()}


def test_every_route_is_public_or_requires_auth(client: TestClient) -> None:
    client.cookies.clear()
    public = public_routes()
    open_routes: list[str] = []
    for route in routes(client):
        if route in public:
            continue
        method, path = route.split(" ", 1)
        response = client.request(method, re.sub(r"\{[^}]+\}", "1", path), json={})
        if response.status_code not in DENIED:
            open_routes.append(f"{route} → {response.status_code}")
    assert not open_routes, (
        "маршруты открыты без входа (нужно 401/403 или внести в security/public-routes.txt "
        f"с решением человека): {open_routes}"
    )


def test_public_list_has_no_stale_routes(client: TestClient) -> None:
    stale = public_routes() - set(routes(client))
    assert not stale, f"в security/public-routes.txt несуществующие маршруты: {sorted(stale)}"


def test_routes_with_ids_have_idor_tests(client: TestClient) -> None:
    covered = {
        " ".join(m.split())
        for path in (ROOT / "tests").rglob("*.py")
        for m in IDOR_MARK.findall(path.read_text())
    }
    need = [r for r in routes(client) if "{" in r and r not in public_routes()]
    missing = [r for r in need if r not in covered]
    assert not missing, (
        "нет теста доступа к чужому ресурсу (IDOR) для маршрутов "
        f'{missing} — @pytest.mark.security("idor", "<METHOD> <path>")'
    )
