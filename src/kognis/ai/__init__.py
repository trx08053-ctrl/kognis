"""Модуль ai: единый интерфейс к языковой модели; провайдер выбирается настройкой."""

from ._app import get_provider
from ._domain import AiError, AiProvider, AiTimeoutError, Message
from ._infra import FakeProvider, HttpSettings, OpenAICompatibleProvider

__all__ = [
    "AiError",
    "AiProvider",
    "AiTimeoutError",
    "FakeProvider",
    "HttpSettings",
    "Message",
    "OpenAICompatibleProvider",
    "get_provider",
]
