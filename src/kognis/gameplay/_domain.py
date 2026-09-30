"""Бизнес-правила игровой механики (D8): XP, уровни, серия дней, достижения. Без ввода-вывода."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from ._achievements import CategoryProgress, HiddenProgress

# Правила опыта (мотивация 2.0) — данные. Награда — за факт действия и отмеченные признаки
# рефлексии, не за длину и не за тон текста.
ENTRY_XP = 10
ENTRY_DAILY_CAP = 3  # записей в день, за которые начисляется XP
DAY_REVIEW_XP = 15
ANSWER_XP = 10  # ответ на уточняющий вопрос разбора
MARK_XP = 5  # за каждую отметку рефлексии
REFLECTION_MAX_XP = 15
DAILY_XP_CAP = 60  # потолок по записям, итогам, ответам разбора и рефлексии за один день

KIND_ENTRY = "entry"
KIND_DAY_REVIEW = "day_review"
KIND_ANSWER = "analysis_answer"
KIND_REFLECTION = "reflection"
KIND_DIRECTION = "direction"  # разбор по направлению (XP 0): нужен только для достижений
CAPPED_KINDS = (KIND_ENTRY, KIND_DAY_REVIEW, KIND_ANSWER, KIND_REFLECTION)

# отметки рефлексии ставит сам пользователь: маленький шаг, хорошее, переформулировка, инсайт
MARKS = ("step", "good", "reframe", "insight")
DEEP_MARKS = frozenset({"step", "insight"})  # «Глубина»: рефлексия с шагом или инсайтом

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
    """Описание старого достижения; у новых (по категориям) текст — в словарях интерфейса."""
    return next((a for a in ACHIEVEMENTS if a.code == code), AchievementDef(code, "", ""))


def is_rewardable_day(day: date, today: date) -> bool:
    """Опыт и серия — за сегодня и последнюю неделю: будущие и давние даты копить нельзя."""
    return today - timedelta(days=BACKDATE_DAYS) <= day <= today


def entry_xp(entries_already_today: int) -> int:
    """XP за очередную запись дня: +10, но только за первые три."""
    return ENTRY_XP if entries_already_today < ENTRY_DAILY_CAP else 0


def clean_marks(marks: Iterable[str]) -> tuple[str, ...]:
    """Известные отметки без повторов, в порядке `MARKS`."""
    given = set(marks)
    return tuple(m for m in MARKS if m in given)


def reflection_bonus(marks: Iterable[str]) -> int:
    """Бонус рефлексии: 5 XP за отметку, не больше 15; без отметок — 0 (длина текста не важна)."""
    return min(REFLECTION_MAX_XP, MARK_XP * len(clean_marks(marks)))


def capped_xp(xp: int, earned_today: int) -> int:
    """Сколько из `xp` можно начислить, если за день уже набрано `earned_today` (потолок 60)."""
    return max(0, min(xp, DAILY_XP_CAP - earned_today))


def level_for(xp: int) -> int:
    reached = sum(1 for threshold in LEVEL_THRESHOLDS if xp >= threshold)
    last = LEVEL_THRESHOLDS[-1]
    return reached + (max(xp, last) - last) // EXTRA_LEVEL_STEP


def level_start(level: int) -> int:
    """Суммарный XP, с которого начинается уровень."""
    listed = min(level, len(LEVEL_THRESHOLDS))
    return LEVEL_THRESHOLDS[listed - 1] + (level - listed) * EXTRA_LEVEL_STEP


def iso_week(day: date) -> tuple[int, int]:
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
        missed = iso_week(prev + timedelta(days=1))
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
    if idle == ONE_MISSED_DAY and iso_week(days[-1] + timedelta(days=1)) not in used:
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
class RecoveryOffer:
    """Обрыв серии, который можно вернуть записью «что помешало» до `expires_on` включительно."""

    streak_before: int
    broken_on: date
    expires_on: date


@dataclass(frozen=True)
class Progress:
    xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    streak: int
    achievements: tuple[EarnedAchievement, ...]
    best_streak: int = 0
    freezes: int = 0
    days_30: int = 0  # дней с дневником за последние 30 — главный показатель
    days_total: int = 0
    weekly_goal: int = 3
    week_days: int = 0  # активных дней в текущей ISO-неделе
    weekend_days: tuple[int, ...] = ()
    recovery: RecoveryOffer | None = None
    categories: tuple[CategoryProgress, ...] = ()  # достижения по категориям и уровням
    hidden: tuple[HiddenProgress, ...] = ()
