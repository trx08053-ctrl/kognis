"""Модуль safety: кризисные сигналы в тексте (локально, без ИИ) и контакты помощи."""

from ._app import HelpBlock, check_text, help_block
from ._domain import DISCLAIMER, Assessment, Contact, assess
from ._infra import crisis_detector_enabled

__all__ = [
    "DISCLAIMER",
    "Assessment",
    "Contact",
    "HelpBlock",
    "assess",
    "check_text",
    "crisis_detector_enabled",
    "help_block",
]
