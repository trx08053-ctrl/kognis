"""Бизнес-правила: без ввода-вывода."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from kognis.errors import CodedError


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class AiError(CodedError):
    """Провайдер ИИ недоступен или ответил неверно; код и параметры безопасны для показа и логов."""


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
