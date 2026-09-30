"""Цифровые герои (мотивация 2.0, 3/4): спутник и наставники. Правила — данные, без ввода-вывода.

Тон по принципам дизайна: ничего не отнимается за пропуск, спутник не регрессирует, а «отдыхает».
Тексты реплик и открыток — в словарях интерфейса (ключи строятся из кодов ниже).
"""

from dataclasses import dataclass
from datetime import date

from kognis.errors import CodedValueError

STAGE_DAYS = (0, 7, 21, 45, 90)  # дней с дневником, с которых начинается стадия 1…5
APPEARANCES = ("fox", "owl", "turtle", "whale")
ADDRESSES = ("ty", "vy")
DEFAULT_ADDRESS = "ty"
MAX_NAME_LENGTH = 24
REST_AFTER_DAYS = 3  # без записей столько дней — спутник «отдыхает» (не болеет, не грустит)
STREAK_RISK_MIN = 2  # мягкая фраза о серии — только когда есть что терять
POSTCARDS_PER_DIRECTION = 5

SITUATIONS = ("intro", "new_stage", "return", "after_summary", "streak_risk")


@dataclass(frozen=True)
class Mentor:
    code: str
    direction: str  # код направления анализа (см. analysis.DIRECTIONS)


MENTORS = (
    Mentor("analyst", "cbt"),
    Mentor("guide", "act"),
    Mentor("gardener", "positive"),
    Mentor("mechanic", "activation"),
)
MENTOR_DIRECTIONS = {m.direction: m.code for m in MENTORS}

# библиотека открыток: направление → коды `<направление>_<n>`; текст — в словаре интерфейса
POSTCARDS = tuple(
    f"{m.direction}_{n}" for m in MENTORS for n in range(1, POSTCARDS_PER_DIRECTION + 1)
)


@dataclass(frozen=True)
class HeroLine:
    hero: str  # «companion» или код наставника
    situation: str


@dataclass(frozen=True)
class Postcard:
    code: str
    for_day: date


def companion_stage(days_total: int) -> int:
    """Стадия 1…5 по числу дней с дневником; не убывает, пока число дней не убывает."""
    return sum(1 for start in STAGE_DAYS if days_total >= start)


def days_to_next_stage(days_total: int) -> int | None:
    """Сколько дней с дневником до следующей стадии; на последней — None."""
    return next((start - days_total for start in STAGE_DAYS if start > days_total), None)


def validate_companion(appearance: str, name: str, address: str) -> str:
    """Проверить выбор пользователя; вернуть имя без пробелов по краям."""
    clean = name.strip()
    if appearance not in APPEARANCES:
        raise CodedValueError("heroes.appearance_unknown")
    if address not in ADDRESSES:
        raise CodedValueError("heroes.address_unknown")
    if not clean or len(clean) > MAX_NAME_LENGTH:
        raise CodedValueError("heroes.name_invalid", max=MAX_NAME_LENGTH)
    return clean


def pick_postcard(owner_id: int, today: date) -> str:
    """Открытка дня: детерминирована (владелец + дата), значит одна в день."""
    return POSTCARDS[(owner_id * 7 + today.toordinal()) % len(POSTCARDS)]


def unlocked_mentors(directions: set[str]) -> list[str]:
    """Коды наставников, чьё направление затронуто разбором или квестом."""
    return [m.code for m in MENTORS if m.direction in directions]


def is_resting(last_active: date | None, today: date) -> bool:
    return last_active is not None and (today - last_active).days >= REST_AFTER_DAYS


@dataclass(frozen=True)
class LineContext:
    stage: int
    stage_seen: int
    last_active: date | None
    reviewed_today: bool
    active_today: bool
    streak: int
    today: date


def choose_line(ctx: LineContext) -> HeroLine | None:
    """Одна реплика спутника на экран: новая стадия, возвращение, итог дня, мягкое о серии."""
    if ctx.stage > ctx.stage_seen:
        return HeroLine("companion", "new_stage")
    if is_resting(ctx.last_active, ctx.today) and not ctx.active_today:
        return HeroLine("companion", "return")  # без упоминания пропуска
    if ctx.reviewed_today:
        return HeroLine("companion", "after_summary")
    gap = (ctx.today - ctx.last_active).days if ctx.last_active else None
    if ctx.streak >= STREAK_RISK_MIN and not ctx.active_today and gap == 1:
        return HeroLine("companion", "streak_risk")  # одно мягкое предложение
    return None
