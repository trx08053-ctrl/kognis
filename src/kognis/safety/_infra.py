"""Конфигурация safety: `KOGNIS_HELP_CONTACTS` (JSON-список {name, phone, note}) и
`KOGNIS_CRISIS_DETECTOR` (on/off, по умолчанию off)."""

import json
import logging
import os

from ._domain import DEFAULT_CONTACTS, Contact

logger = logging.getLogger(__name__)


def crisis_detector_enabled() -> bool:
    """Единственное место чтения настройки: детектор включён только явным `on`."""
    return os.environ.get("KOGNIS_CRISIS_DETECTOR", "").strip().lower() == "on"


def load_contacts() -> tuple[Contact, ...]:
    raw = os.environ.get("KOGNIS_HELP_CONTACTS", "").strip()
    if not raw:
        return DEFAULT_CONTACTS
    try:
        items = json.loads(raw)
        contacts = tuple(
            Contact(str(i["name"]), str(i["phone"]), str(i.get("note", ""))) for i in items
        )
    except (ValueError, KeyError, TypeError):
        # человеку в кризисе контакты нужны всегда: битая конфигурация не должна ломать ответ
        logger.error("KOGNIS_HELP_CONTACTS: ожидается JSON-список {name, phone}; взят 112")
        return DEFAULT_CONTACTS
    return contacts or DEFAULT_CONTACTS
