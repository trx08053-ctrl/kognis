"""Сценарии модуля; публичное — реэкспорт в __init__.py."""

from dataclasses import dataclass

from ._domain import SUPPORT_MESSAGE, Assessment, Contact, assess
from ._infra import crisis_detector_enabled, load_contacts


@dataclass(frozen=True)
class HelpBlock:
    message: str
    contacts: tuple[Contact, ...]


def help_block() -> HelpBlock:
    """Блок помощи для ответа пользователю; контакты — из конфигурации (по умолчанию 112)."""
    return HelpBlock(SUPPORT_MESSAGE, load_contacts())


def check_text(text: str) -> tuple[Assessment, HelpBlock | None]:
    """Оценка текста и, при кризисном сигнале, блок помощи.

    При выключенном детекторе (`KOGNIS_CRISIS_DETECTOR`, по умолчанию off) сигналов нет.
    """
    if not crisis_detector_enabled():
        return Assessment(crisis=False), None
    assessment = assess(text)
    return assessment, (help_block() if assessment.crisis else None)
