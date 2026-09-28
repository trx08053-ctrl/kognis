"""Контакты помощи — конфигурация: `KOGNIS_HELP_CONTACTS` (JSON-список {name, phone, note})."""

import json
import logging
import os

from ._domain import DEFAULT_CONTACTS, Contact

logger = logging.getLogger(__name__)


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
