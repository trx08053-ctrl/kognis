"""Серия «Нить» (мотивация 2.0, ADR 0006): запас заморозок, выходные, восстановление.

Без ввода-вывода. Правила — данные (константы ниже). Серия считается заново из дат активности:
состояние не хранится. Ничего не отнимается за пропуск: заморозка тратится сама, а оборванную
серию можно вернуть в окне 72 часов.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from ._domain import ONE_MISSED_DAY, iso_week

FREEZE_STOCK_START = 2  # у нового пользователя
FREEZE_STOCK_MAX = 2
ACTIVE_DAYS_PER_FREEZE = 7  # +1 заморозка за каждые 7 активных дней (не больше запаса)
DAYS_IN_WEEK = 7
MAX_WEEKEND_DAYS = 2  # «выходных» дней недели по выбору: не рвут серию и не продлевают её
RECOVERY_WINDOW_DAYS = 3  # 72 часа: локальные даты после первого пропущенного дня
MIN_RECOVERABLE_STREAK = 2  # короткую серию (1 день) «восстанавливать» нечего
RECENT_DAYS = 30  # главный показатель экрана: дней с дневником за последние 30

WEEKLY_GOALS = (3, 5, 7)  # активных дней в неделю на выбор
DEFAULT_WEEKLY_GOAL = 3
WEEKLY_GOAL_XP = 30
KIND_WEEKLY_GOAL = "weekly_goal"


@dataclass(frozen=True)
class StreakRules:
    weekend_days: frozenset[int] = frozenset()  # `date.weekday()`: 0 — понедельник
    # до этой даты действует прежнее правило (одна бесплатная заморозка на ISO-неделю): серии
    # существующих пользователей при переходе не уменьшаются; None — новые правила с начала
    rules_from: date | None = None
    # дни последней активности перед обрывами, которые пользователь восстановил
    recovered: frozenset[date] = frozenset()


@dataclass(frozen=True)
class Break:
    after_day: date  # последняя активность перед обрывом (идентификатор обрыва)
    broken_on: date  # первый пропущенный день, который нечем было закрыть
    streak_before: int


@dataclass(frozen=True)
class StreakState:
    current: int
    best: int
    freezes: int
    breaks: tuple[Break, ...]  # невосстановленные обрывы по порядку


@dataclass(frozen=True)
class _Gap:
    stock: int  # запас заморозок после закрытия пропущенных дней
    broken_on: date | None = None  # первый день, который нечем закрыть; None — серия не прервалась


def _cross(
    prev: date, end: date, stock: int, used: set[tuple[int, int]], rules: StreakRules
) -> _Gap:
    """Закрыть пропущенные дни строго между `prev` и `end`: что осталось в запасе или где обрыв."""
    first = prev + timedelta(days=1)
    missed = (end - first).days
    if missed <= 0:
        return _Gap(stock)
    if rules.rules_from is not None and end < rules.rules_from:
        if missed == ONE_MISSED_DAY - 1 and iso_week(first) not in used:
            used.add(iso_week(first))
            return _Gap(stock)
        return _Gap(stock, first)
    for offset in range(missed):
        day = first + timedelta(days=offset)
        if day.weekday() in rules.weekend_days:
            continue
        if prev in rules.recovered:
            return _Gap(stock)
        if stock == 0:
            return _Gap(0, day)
        stock -= 1
    return _Gap(stock)


def streak_state(active_days: Iterable[date], today: date, rules: StreakRules) -> StreakState:
    """Текущая и лучшая серия, запас заморозок и обрывы на `today` (локальная дата пользователя).

    Каждый пропущенный день (кроме выходных) тратит одну заморозку; нечем закрыть — обрыв, серия
    начинается заново. Заморозки и выходные серию не удлиняют; +1 заморозка за каждые 7 активных
    дней.
    """
    days = sorted({d for d in active_days if d <= today})
    if not days:
        return StreakState(0, 0, FREEZE_STOCK_START, ())
    stock, streak, best, earned = FREEZE_STOCK_START, 1, 1, 0
    used: set[tuple[int, int]] = set()
    breaks: list[Break] = []

    def count_active(day: date) -> None:
        nonlocal stock, earned
        if rules.rules_from is None or day >= rules.rules_from:
            earned += 1
            if earned % ACTIVE_DAYS_PER_FREEZE == 0:
                stock = min(FREEZE_STOCK_MAX, stock + 1)

    count_active(days[0])
    for prev, cur in pairwise(days):
        gap = _cross(prev, cur, stock, used, rules)
        stock = gap.stock
        if gap.broken_on is None:
            streak += 1
        else:
            breaks.append(Break(prev, gap.broken_on, streak))
            streak = 1
        best = max(best, streak)
        count_active(cur)
    tail = _cross(days[-1], today, stock, set(used), rules)
    if tail.broken_on is not None:
        breaks.append(Break(days[-1], tail.broken_on, streak))
        streak = 0
    return StreakState(streak, best, tail.stock, tuple(breaks))


def recoverable_break(state: StreakState, today: date) -> Break | None:
    """Обрыв, который ещё можно вернуть: последний, не старше 72 часов, серия до него ≥ 2 дней."""
    for brk in reversed(state.breaks):
        age = (today - brk.broken_on).days
        if brk.streak_before >= MIN_RECOVERABLE_STREAK and 0 <= age <= RECOVERY_WINDOW_DAYS:
            return brk
    return None


def days_with_diary(active_days: Iterable[date], today: date) -> tuple[int, int]:
    """(дней с дневником за последние 30, всего дней)."""
    days = {d for d in active_days if d <= today}
    start = today - timedelta(days=RECENT_DAYS - 1)
    return sum(1 for d in days if d >= start), len(days)


def active_days_in_week(active_days: Iterable[date], today: date) -> int:
    """Активных дней в текущей ISO-неделе `today`."""
    return len({d for d in active_days if d <= today and iso_week(d) == iso_week(today)})


def week_ref(day: date) -> str:
    """Источник бонуса недели: по одному событию на ISO-неделю."""
    year, week = iso_week(day)
    return f"{year}-W{week:02d}"
