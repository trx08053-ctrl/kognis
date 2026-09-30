"""Ошибки для показа человеку: код и параметры вместо фразы (docs/I18N.md, правило 2).

Текст по коду берёт интерфейс из словаря (`error.<code>`); сообщение исключения — служебное.
"""

from typing import Any


class CodedError(Exception):
    """Ошибка с кодом вида `area.reason` и параметрами для подстановки в текст."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


class CodedValueError(CodedError, ValueError):
    """Неверный ввод с кодом: остаётся ValueError для обработчиков `except ValueError`."""
