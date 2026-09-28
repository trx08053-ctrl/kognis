"""Модуль access: решает, доступна ли пользователю функция (D9); сейчас — всегда да."""

from ._domain import Feature, can_use

__all__ = ["Feature", "can_use"]
