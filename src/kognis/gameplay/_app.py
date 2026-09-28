"""Сценарии gameplay: начисление XP и чтение прогресса. Действия вызывает слой web (D2)."""

from datetime import date

from sqlalchemy.orm import Session

from ._domain import (
    DAY_REVIEW_XP,
    KIND_DAY_REVIEW,
    KIND_ENTRY,
    EarnedAchievement,
    Progress,
    achievement_def,
    earned_achievements,
    entry_xp,
    is_rewardable_day,
    level_for,
    level_start,
    streak_length,
)
from ._infra import ProgressRepository


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

    def _grant(self, owner_id: int, today: date) -> Progress:
        streak = streak_length(self._repo.active_days(owner_id), today)
        have = [code for code, _ in self._repo.achievements(owner_id)]
        for code in earned_achievements(
            entries=self._repo.count_events(owner_id, KIND_ENTRY),
            reviews=self._repo.count_events(owner_id, KIND_DAY_REVIEW),
            streak=streak,
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
        return Progress(
            xp=xp,
            level=level,
            level_start_xp=level_start(level),
            next_level_xp=level_start(level + 1),
            streak=streak_length(self._repo.active_days(owner_id), today),
            achievements=tuple(earned),
        )
