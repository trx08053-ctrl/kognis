"""Бизнес-правила игровой механики (D8): XP, уровни, серия дней, достижения. Без ввода-вывода."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

ENTRY_XP = 10
ENTRY_DAILY_CAP = 3  # записей в день, за которые начисляется XP
DAY_REVIEW_XP = 20

KIND_ENTRY = "entry"
KIND_DAY_REVIEW = "day_review"

BACKDATE_DAYS = 7  # насколько назад можно записать день и получить за него опыт
ONE_MISSED_DAY = 2  # разница дат при ровно одном пропущенном дне между активными

# суммарный XP, с которого начинается уровень (уровень 1 — с нуля);
# дальше каждый следующий уровень требует ещё EXTRA_LEVEL_STEP
LEVEL_THRESHOLDS = (0, 50, 120, 210, 320, 450, 600, 780, 1000, 1250)
EXTRA_LEVEL_STEP = 300


@dataclass(frozen=True)
class AchievementDef:
    code: str
    title: str
    description: str


ACHIEVEMENTS = (
    AchievementDef("first_entry", "Первая запись", "Сделана первая запись в дневнике"),
    AchievementDef("streak_3", "Серия 3 дня", "Три дня подряд с записью или итогом дня"),
    AchievementDef("streak_7", "Серия 7 дней", "Неделя подряд с записью или итогом дня"),
    AchievementDef("streak_30", "Серия 30 дней", "Месяц подряд с записью или итогом дня"),
    AchievementDef("reviews_10", "10 итогов дня", "Подведено десять итогов дня"),
)
STREAK_ACHIEVEMENTS = {"streak_3": 3, "streak_7": 7, "streak_30": 30}
REVIEWS_FOR_ACHIEVEMENT = 10


def achievement_def(code: str) -> AchievementDef:
    return next(a for a in ACHIEVEMENTS if a.code == code)


def is_rewardable_day(day: date, today: date) -> bool:
    """Опыт и серия — за сегодня и последнюю неделю: будущие и давние даты копить нельзя."""
    return today - timedelta(days=BACKDATE_DAYS) <= day <= today


def entry_xp(entries_already_today: int) -> int:
    """XP за очередную запись дня: +10, но только за первые три."""
    return ENTRY_XP if entries_already_today < ENTRY_DAILY_CAP else 0


def level_for(xp: int) -> int:
    extra = xp - LEVEL_THRESHOLDS[-1]
    if extra >= 0:
        return len(LEVEL_THRESHOLDS) + extra // EXTRA_LEVEL_STEP
    return sum(1 for threshold in LEVEL_THRESHOLDS if xp >= threshold)


def level_start(level: int) -> int:
    """Суммарный XP, с которого начинается уровень."""
    if level <= len(LEVEL_THRESHOLDS):
        return LEVEL_THRESHOLDS[level - 1]
    return LEVEL_THRESHOLDS[-1] + (level - len(LEVEL_THRESHOLDS)) * EXTRA_LEVEL_STEP


def _week(day: date) -> tuple[int, int]:
    iso = day.isocalendar()
    return (iso.year, iso.week)


def streak_length(active_days: Iterable[date], today: date) -> int:
    """Серия дней подряд с активностью на `today` (локальная дата пользователя).

    Пропуск ровно одного дня гасится заморозкой — одной на неделю (ISO, пн–вс, неделя
    пропущенного дня); больший пропуск или вторая заморозка за неделю сбрасывают серию.
    Заморозка серию не увеличивает. Серия жива, если с последней активности прошло
    не больше суток; двое суток — только если пропущенный день ещё можно заморозить.
    """
    days = sorted({d for d in active_days if d <= today})
    if not days:
        return 0
    used: set[tuple[int, int]] = set()
    streak = 1
    for prev, cur in pairwise(days):
        gap = (cur - prev).days
        missed = _week(prev + timedelta(days=1))
        if gap == 1:
            streak += 1
        elif gap == ONE_MISSED_DAY and missed not in used:
            used.add(missed)
            streak += 1
        else:
            streak = 1
    idle = (today - days[-1]).days
    if idle <= 1:
        return streak
    if idle == ONE_MISSED_DAY and _week(days[-1] + timedelta(days=1)) not in used:
        return streak
    return 0


def earned_achievements(
    *, entries: int, reviews: int, streak: int, already: Iterable[str]
) -> list[str]:
    """Коды достижений, условия которых выполнены и которые ещё не выданы."""
    have = set(already)
    wanted: list[str] = []
    if entries >= 1:
        wanted.append("first_entry")
    wanted += [code for code, need in STREAK_ACHIEVEMENTS.items() if streak >= need]
    if reviews >= REVIEWS_FOR_ACHIEVEMENT:
        wanted.append("reviews_10")
    return [code for code in wanted if code not in have]


@dataclass(frozen=True)
class EarnedAchievement:
    code: str
    title: str
    description: str
    earned_on: date


@dataclass(frozen=True)
class Progress:
    xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    streak: int
    achievements: tuple[EarnedAchievement, ...]
