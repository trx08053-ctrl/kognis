"""Бизнес-правила анализа периода: направления, формат ответа модели, динамика настроения."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_PERIOD_DAYS = 92
MAX_ENTRIES = 100
MAX_ANSWERS = 10
MAX_ANSWER_LENGTH = 2_000
MIN_TREND_DELTA = 0.5


@dataclass(frozen=True)
class Direction:
    code: str
    title: str
    focus: str


# Данные-конфигурация (D7): направление задаёт только «линзу» для модели.
DIRECTIONS: tuple[Direction, ...] = (
    Direction(
        "cbt",
        "КПТ",
        "автоматические мысли, когнитивные искажения, связь мысли, эмоции и поведения",
    ),
    Direction(
        "act",
        "ACT",
        "избегание, слияние с мыслями, принятие, ценности и действия в их русле",
    ),
    Direction(
        "schema",
        "Схема-терапия",
        "повторяющиеся схемы и режимы, неудовлетворённые базовые потребности",
    ),
    Direction(
        "positive",
        "Позитивная психология",
        "сильные стороны, благодарность, смысл, вовлечённость, ресурсы",
    ),
    Direction(
        "activation",
        "Поведенческая активация",
        "связь активности и настроения, избегание, небольшие приятные и значимые действия",
    ),
)


def direction_by_code(code: str) -> Direction:
    for direction in DIRECTIONS:
        if direction.code == code:
            return direction
    raise ValueError("неизвестное направление")


class Pattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    entry_ids: list[int] = Field(min_length=1, max_length=20)
    quotes: list[str] = Field(default_factory=list, max_length=5)


class AnalysisResult(BaseModel):
    """Строгий формат ответа модели: лишние поля и пустые части недопустимы."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=4_000)
    patterns: list[Pattern] = Field(max_length=10)
    questions: list[str] = Field(max_length=5)
    quest_ideas: list[str] = Field(default_factory=list, max_length=5)


class InvalidModelAnswerError(ValueError):
    """Ответ модели не соответствует формату."""


def parse_result(raw: str, known_entry_ids: frozenset[int]) -> AnalysisResult:
    """Разбор ответа модели; опоры обязаны ссылаться на переданные записи."""
    try:
        result = AnalysisResult.model_validate(json.loads(raw))
    except (ValueError, ValidationError):
        raise InvalidModelAnswerError("ответ модели не соответствует формату") from None
    for pattern in result.patterns:
        if not set(pattern.entry_ids) <= known_entry_ids:
            raise InvalidModelAnswerError("паттерн ссылается на неизвестную запись")
    return result


@dataclass(frozen=True)
class Analysis:
    id: int
    owner_id: int
    parent_id: int | None
    direction: str
    start: date
    end: date
    status: Literal["done", "crisis"]
    result: AnalysisResult | None
    answers: tuple[str, ...]


def validate_period(start: date, end: date) -> None:
    if end < start:
        raise ValueError("конец периода раньше начала")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise ValueError(f"период не длиннее {MAX_PERIOD_DAYS} дней")


def normalize_answers(raw: Sequence[str]) -> tuple[str, ...]:
    answers = tuple(a.strip() for a in raw if a.strip())
    if not answers:
        raise ValueError("нужен хотя бы один ответ")
    if len(answers) > MAX_ANSWERS or any(len(a) > MAX_ANSWER_LENGTH for a in answers):
        raise ValueError("ответы слишком длинные или их слишком много")
    return answers


@dataclass(frozen=True)
class MoodPoint:
    day: date
    mood: int
    wellbeing: int


@dataclass(frozen=True)
class MoodDynamics:
    points: tuple[MoodPoint, ...]
    average_mood: float | None
    average_wellbeing: float | None
    trend: Literal["up", "down", "flat", "unknown"]


def _mean(values: Sequence[int]) -> float:
    return sum(values) / len(values)


def mood_dynamics(points: Sequence[MoodPoint]) -> MoodDynamics:
    """Динамика по итогам дня, без ИИ: средние и тренд (вторая половина периода против первой)."""
    ordered = tuple(sorted(points, key=lambda p: p.day))
    if not ordered:
        return MoodDynamics((), None, None, "unknown")
    moods = [p.mood for p in ordered]
    trend: Literal["up", "down", "flat", "unknown"] = "unknown"
    half = len(moods) // 2
    if half:
        delta = _mean(moods[len(moods) - half :]) - _mean(moods[:half])
        trend = (
            "up" if delta >= MIN_TREND_DELTA else "down" if delta <= -MIN_TREND_DELTA else "flat"
        )
    return MoodDynamics(ordered, _mean(moods), _mean([p.wellbeing for p in ordered]), trend)
