"""Необработанная ошибка не раскрывает внутренние детали (ASVS V7)."""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.web import create_app


def test_unhandled_error_hides_details(engine: Engine) -> None:
    app = create_app(engine, clock=lambda: dt.datetime(2026, 9, 1, 12, tzinfo=dt.UTC))

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("внутренняя деталь-XYZ")

    app.router.routes.insert(0, app.router.routes.pop())  # раньше SPA-маршрута «всё остальное»
    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert "XYZ" not in response.text
    assert "Traceback" not in response.text
    assert "default-src" in response.headers["content-security-policy"]
