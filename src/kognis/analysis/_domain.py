"""Бизнес-правила анализа периода: направления, формат ответа модели, динамика настроения."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kognis.errors import CodedValueError

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
    raise CodedValueError("analysis.direction_unknown")


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
    """Ответ модели не соответствует формату; `problems` — путь поля и суть, без текстов записей."""

    def __init__(self, message: str, problems: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.problems = tuple(problems)


def _problems(err: ValidationError) -> list[str]:
    """Ошибки валидации без входных значений: в них могут быть тексты записей."""
    return [
        f"{'.'.join(str(part) for part in e['loc']) or '(root)'}: {e['msg']}"[:200]
        for e in err.errors(include_url=False, include_input=False, include_context=False)
    ]


def parse_result(raw: str, known_entry_ids: frozenset[int]) -> AnalysisResult:
    """Разбор ответа модели; опоры обязаны ссылаться на переданные записи."""
    fmt = "model answer does not match the format"
    try:
        result = AnalysisResult.model_validate(json.loads(raw))
    except ValidationError as err:
        raise InvalidModelAnswerError(fmt, _problems(err)) from None
    except ValueError:
        raise InvalidModelAnswerError(fmt, ["(root): answer is not JSON"]) from None
    for i, pattern in enumerate(result.patterns):
        if not set(pattern.entry_ids) <= known_entry_ids:
            raise InvalidModelAnswerError(
                "pattern references an unknown entry",
                [f"patterns.{i}.entry_ids: ids not present in the given entries"],
            )
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
        raise CodedValueError("analysis.period_reversed")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise CodedValueError("analysis.period_long", max=MAX_PERIOD_DAYS)


def normalize_answers(raw: Sequence[str]) -> tuple[str, ...]:
    answers = tuple(a.strip() for a in raw if a.strip())
    if not answers:
        raise CodedValueError("analysis.answers_empty")
    if len(answers) > MAX_ANSWERS or any(len(a) > MAX_ANSWER_LENGTH for a in answers):
        raise CodedValueError("analysis.answers_long")
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
