"""Модуль web: HTTP-вход приложения — страницы, JSON API, /health. Бизнес-логики не содержит."""

import os

import uvicorn

from ._app import create_app


def main() -> None:
    """Запуск сервера: HOST/PORT из окружения (по умолчанию 127.0.0.1:8000)."""
    uvicorn.run(
        create_app(),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )


__all__ = ["create_app", "main"]
