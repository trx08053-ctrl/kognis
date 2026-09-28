"""Правила пользователей: чистая логика без ввода-вывода."""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    name: str


def normalize_name(raw: str) -> str:
    """Имя без пробелов по краям; пустое имя недопустимо."""
    name = raw.strip()
    if not name:
        raise ValueError("имя не может быть пустым")
    return name
