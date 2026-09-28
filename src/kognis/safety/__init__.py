"""Модуль safety: кризисные сигналы в тексте (локально, без ИИ) и контакты помощи."""

from ._app import HelpBlock, check_text, help_block
from ._domain import DISCLAIMER, Assessment, Contact, assess

__all__ = [
    "DISCLAIMER",
    "Assessment",
    "Contact",
    "HelpBlock",
    "assess",
    "check_text",
    "help_block",
]
