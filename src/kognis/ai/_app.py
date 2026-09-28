"""Сценарии модуля; публичное — реэкспорт в __init__.py."""

import os

from ._domain import AiProvider
from ._infra import FakeProvider, OpenAICompatibleProvider


def get_provider() -> AiProvider:
    """Провайдер по конфигурации: без `KOGNIS_AI_BASE_URL` — FakeProvider."""
    base_url = os.environ.get("KOGNIS_AI_BASE_URL", "").strip()
    if not base_url:
        return FakeProvider()
    return OpenAICompatibleProvider(
        base_url,
        os.environ.get("KOGNIS_AI_MODEL", "").strip(),
        os.environ.get("KOGNIS_AI_API_KEY", "").strip(),
    )
