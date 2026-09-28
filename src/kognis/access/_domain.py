"""Бизнес-правила доступа к функциям (D9): сейчас доступно всё, тарифы — позже."""

from enum import StrEnum


class Feature(StrEnum):
    AI_ANALYSIS = "ai_analysis"
    ADVANCED_CHARTS = "advanced_charts"


def can_use(user_id: int, feature: Feature | str) -> bool:
    """Можно ли пользователю пользоваться функцией. Точка расширения под тарифы."""
    Feature(feature)  # неизвестная функция — ValueError, а не молчаливое «да»
    return user_id > 0
