"""Контакты помощи — конфигурация: `KOGNIS_HELP_CONTACTS` (JSON-список {name, phone, note})."""

import json
import os

from ._domain import DEFAULT_CONTACTS, Contact


def load_contacts() -> tuple[Contact, ...]:
    raw = os.environ.get("KOGNIS_HELP_CONTACTS", "").strip()
    if not raw:
        return DEFAULT_CONTACTS
    try:
        items = json.loads(raw)
        contacts = tuple(
            Contact(str(i["name"]), str(i["phone"]), str(i.get("note", ""))) for i in items
        )
    except (ValueError, KeyError, TypeError) as err:
        raise ValueError("KOGNIS_HELP_CONTACTS: ожидается JSON-список {name, phone}") from err
    return contacts or DEFAULT_CONTACTS
