"""Сценарии gameplay: начисление XP и чтение прогресса. Действия вызывает слой web (D2)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from kognis.errors import CodedError, CodedValueError

from ._domain import (
    DAY_REVIEW_XP,
    KIND_DAY_REVIEW,
    KIND_ENTRY,
    EarnedAchievement,
    Progress,
    RecoveryOffer,
    achievement_def,
    earned_achievements,
    entry_xp,
    is_rewardable_day,
    level_for,
    level_start,
)
from ._infra import ProgressRepository
from ._streak import (
    DAYS_IN_WEEK,
    DEFAULT_WEEKLY_GOAL,
    KIND_WEEKLY_GOAL,
    MAX_WEEKEND_DAYS,
    RECOVERY_WINDOW_DAYS,
    WEEKLY_GOAL_XP,
    WEEKLY_GOALS,
    StreakRules,
    StreakState,
    active_days_in_week,
    days_with_diary,
    recoverable_break,
    streak_state,
    week_ref,
)


class RecoveryUnavailableError(CodedError):
    """Вернуть нечего: нет обрыва, окно 72 часов прошло или обрыв уже восстановлен."""

    def __init__(self) -> None:
        super().__init__("progress.recovery_unavailable")


class GameplayService:
    def __init__(self, session: Session) -> None:
        self._repo = ProgressRepository(session)

    def award_entry(self, owner_id: int, entry_id: int, day: date, today: date) -> Progress:
        """Запись за `day`: +10 XP, но не более трёх записей в день; за одну запись — один раз.

        Сверх лимита событие пишется с 0 XP — день всё равно считается активным для серии.
        """
        ref = str(entry_id)
        if is_rewardable_day(day, today) and not self._repo.has_event(owner_id, KIND_ENTRY, ref):
            xp = entry_xp(self._repo.count_events(owner_id, KIND_ENTRY, day))
            self._repo.add_event(owner_id, KIND_ENTRY, ref, day, xp)
        return self._grant(owner_id, today)

    def award_day_review(self, owner_id: int, day: date, today: date) -> Progress:
        """Итог дня за `day`: +20 XP один раз за дату (повторное сохранение XP не даёт)."""
        ref = day.isoformat()
        rewardable = is_rewardable_day(day, today)
        if rewardable and not self._repo.has_event(owner_id, KIND_DAY_REVIEW, ref):
            self._repo.add_event(owner_id, KIND_DAY_REVIEW, ref, day, DAY_REVIEW_XP)
        return self._grant(owner_id, today)

    def progress(self, owner_id: int, today: date) -> Progress:
        return self._snapshot(owner_id, today)

    def save_settings(
        self, owner_id: int, weekend_days: list[int], weekly_goal: int, today: date
    ) -> Progress:
        """Выходные дни (0–2 дня недели, 0 — пн) и недельная цель (3/5/7 дней)."""
        if weekly_goal not in WEEKLY_GOALS:
            raise CodedValueError("progress.goal_invalid")
        unique = frozenset(weekend_days)
        if len(unique) > MAX_WEEKEND_DAYS or not all(0 <= d < DAYS_IN_WEEK for d in unique):
            raise CodedValueError("progress.weekend_invalid", max=MAX_WEEKEND_DAYS)
        self._repo.save_settings(owner_id, unique, weekly_goal)
        return self._grant(owner_id, today)

    def recover(self, owner_id: int, note: str, today: date) -> Progress:
        """Вернуть оборванную серию записью «что помешало»: одна на обрыв, в течение 72 часов."""
        state = self._state(owner_id, today)[0]
        offer = recoverable_break(state, today)
        if offer is None:
            raise RecoveryUnavailableError
        if not self._repo.add_recovery(owner_id, offer.after_day, offer.broken_on, note.strip()):
            raise RecoveryUnavailableError
        return self._grant(owner_id, today)

    def _state(self, owner_id: int, today: date) -> tuple[StreakState, int, StreakRules]:
        settings = self._repo.settings(owner_id)
        weekend, goal, rules_from = settings or (frozenset[int](), DEFAULT_WEEKLY_GOAL, None)
        rules = StreakRules(weekend, rules_from, self._repo.recovered_after_days(owner_id))
        return streak_state(self._repo.active_days(owner_id), today, rules), goal, rules

    def _grant(self, owner_id: int, today: date) -> Progress:
        streak, goal, _ = self._state(owner_id, today)
        week_done = active_days_in_week(self._repo.active_days(owner_id), today)
        ref = week_ref(today)
        if week_done >= goal and not self._repo.has_event(owner_id, KIND_WEEKLY_GOAL, ref):
            self._repo.add_event(owner_id, KIND_WEEKLY_GOAL, ref, today, WEEKLY_GOAL_XP)
        have = [code for code, _ in self._repo.achievements(owner_id)]
        for code in earned_achievements(
            entries=self._repo.count_events(owner_id, KIND_ENTRY),
            reviews=self._repo.count_events(owner_id, KIND_DAY_REVIEW),
            streak=streak.current,
            already=have,
        ):
            self._repo.add_achievement(owner_id, code, today)
        return self._snapshot(owner_id, today)

    def _snapshot(self, owner_id: int, today: date) -> Progress:
        xp = self._repo.total_xp(owner_id)
        level = level_for(xp)
        earned: list[EarnedAchievement] = []
        for code, earned_on in self._repo.achievements(owner_id):
            definition = achievement_def(code)
            earned.append(
                EarnedAchievement(code, definition.title, definition.description, earned_on)
            )
        streak, goal, rules = self._state(owner_id, today)
        days = self._repo.active_days(owner_id)
        days_30, days_total = days_with_diary(days, today)
        brk = recoverable_break(streak, today)
        offer = (
            RecoveryOffer(
                brk.streak_before, brk.broken_on, brk.broken_on + timedelta(RECOVERY_WINDOW_DAYS)
            )
            if brk
            else None
        )
        return Progress(
            xp=xp,
            level=level,
            level_start_xp=level_start(level),
            next_level_xp=level_start(level + 1),
            streak=streak.current,
            achievements=tuple(earned),
            best_streak=streak.best,
            freezes=streak.freezes,
            days_30=days_30,
            days_total=days_total,
            weekly_goal=goal,
            week_days=active_days_in_week(days, today),
            weekend_days=tuple(sorted(rules.weekend_days)),
            recovery=offer,
        )
