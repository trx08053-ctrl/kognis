"""Достижения по уровням и категориям (мотивация 2.0). Без ввода-вывода; правила — данные.

Ничего не выдаётся за грустные записи и за количество текста: считаются дни, отметки рефлексии,
разные направления разборов и квизы, выполненные шаги квестов.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

LEVELS = ("bronze", "silver", "gold")
DIRECTIONS_TOTAL = 5  # направлений разбора (analysis.DIRECTIONS; сверяет тест на слое web)
QUIZZES_TOTAL = 3  # квизов-рефлексий (`QUIZZES`; сверяет тест)

# категория → пороги трёх уровней (метрика описана в `Metrics`)
CATEGORY_TARGETS: dict[str, tuple[int, int, int]] = {
    "consistency": (7, 30, 100),  # дней с дневником
    "depth": (5, 25, 100),  # рефлексий с шагом или инсайтом
    "explorer": (2, 4, DIRECTIONS_TOTAL + QUIZZES_TOTAL),  # разные направления и квизы
    "care": (5, 25, 100),  # выполненных шагов квестов
}
HIDDEN = ("comeback", "first_gratitude", "year_diary")
PAUSE_DAYS = 7  # пауза в днях без записей, после которой возвращение тёплое
YEAR_DAYS = 365


def level_code(category: str, level: int) -> str:
    """Код достижения: `consistency_1` — бронза, `_2` — серебро, `_3` — золото."""
    return f"{category}_{level}"


@dataclass(frozen=True)
class Metrics:
    active_days: frozenset[date]
    deep_reflections: int
    gratitude: bool  # хотя бы раз отмечено «хорошее»
    explored: int  # разные направления разборов + разные квизы
    care_steps: int
    today: date

    def value(self, category: str) -> int:
        return {
            "consistency": len(self.active_days),
            "depth": self.deep_reflections,
            "explorer": self.explored,
            "care": self.care_steps,
        }[category]


@dataclass(frozen=True)
class LevelProgress:
    code: str
    level: int  # 1–3
    target: int
    earned_on: date | None


@dataclass(frozen=True)
class CategoryProgress:
    category: str
    value: int
    levels: tuple[LevelProgress, ...]
    next_target: int | None  # порог следующего уровня; None — все три получены


@dataclass(frozen=True)
class HiddenProgress:
    code: str
    earned_on: date | None  # пока не получено — интерфейс показывает «?»


def came_back(days: Iterable[date]) -> bool:
    """Был перерыв в `PAUSE_DAYS` дней и больше, после которого дневник снова ведётся."""
    ordered = sorted(set(days))
    return any((b - a).days > PAUSE_DAYS for a, b in pairwise(ordered))


def hidden_earned(metrics: Metrics) -> list[str]:
    """Тёплые скрытые достижения, условия которых выполнены."""
    codes: list[str] = []
    if came_back(metrics.active_days):
        codes.append("comeback")
    if metrics.gratitude:
        codes.append("first_gratitude")
    if metrics.active_days and min(metrics.active_days) <= metrics.today - timedelta(YEAR_DAYS):
        codes.append("year_diary")
    return codes


def earned_levels(metrics: Metrics) -> list[str]:
    """Коды достижений категорий, условия которых выполнены (без учёта уже выданных)."""
    return [
        level_code(category, i)
        for category, targets in CATEGORY_TARGETS.items()
        for i, target in enumerate(targets, 1)
        if metrics.value(category) >= target
    ]


def achievements_due(metrics: Metrics, already: Iterable[str]) -> list[str]:
    have = set(already)
    wanted = earned_levels(metrics) + hidden_earned(metrics)
    return [code for code in wanted if code not in have]


def catalog(
    metrics: Metrics, earned_on: dict[str, date]
) -> tuple[tuple[CategoryProgress, ...], tuple[HiddenProgress, ...]]:
    """Сетка экрана: по категориям — прогресс до следующего уровня; скрытые — «?» до получения."""
    categories: list[CategoryProgress] = []
    for category, targets in CATEGORY_TARGETS.items():
        levels = tuple(
            LevelProgress(
                level_code(category, i), i, target, earned_on.get(level_code(category, i))
            )
            for i, target in enumerate(targets, 1)
        )
        pending = [lv.target for lv in levels if lv.earned_on is None]
        categories.append(
            CategoryProgress(category, metrics.value(category), levels, min(pending, default=None))
        )
    hidden = tuple(HiddenProgress(code, earned_on.get(code)) for code in HIDDEN)
    return tuple(categories), hidden
