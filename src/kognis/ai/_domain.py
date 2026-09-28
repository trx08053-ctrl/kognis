"""Бизнес-правила: без ввода-вывода."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class AiError(Exception):
    """Провайдер ИИ недоступен или ответил неверно; текст безопасен для показа и логов."""


class AiTimeoutError(AiError):
    """Провайдер не ответил за отведённое время."""


class AiProvider(Protocol):
    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        schema: dict[str, Any] | None = None,
    ) -> str:
        """Ответ модели текстом; при `schema` (JSON Schema) — строка с JSON по схеме."""
        ...
