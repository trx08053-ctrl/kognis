"""Сценарии gameplay: начисление XP и чтение прогресса. Действия вызывает слой web (D2)."""

from collections.abc import Iterable
from datetime import date, timedelta

from sqlalchemy.orm import Session

from kognis.errors import CodedError, CodedValueError

from ._achievements import Metrics, achievements_due, catalog
from ._domain import (
    ANSWER_XP,
    CAPPED_KINDS,
    DAY_REVIEW_XP,
    DEEP_MARKS,
    KIND_ANSWER,
    KIND_DAY_REVIEW,
    KIND_DIRECTION,
    KIND_ENTRY,
    KIND_REFLECTION,
    EarnedAchievement,
    Progress,
    RecoveryOffer,
    achievement_def,
    capped_xp,
    clean_marks,
    earned_achievements,
    entry_xp,
    is_rewardable_day,
    level_for,
    level_start,
    reflection_bonus,
)
from ._infra import ProgressRepository
from ._quests import KIND_QUEST_STEP, KIND_QUIZ
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

    def award_entry(
        self,
        owner_id: int,
        entry_id: int,
        day: date,
        today: date,
        marks: Iterable[str] = (),
    ) -> Progress:
        """Запись за `day`: +10 XP, но не более трёх записей в день; за одну запись — один раз.

        Сверх лимита событие пишется с 0 XP — день всё равно считается активным для серии.
        Отметки рефлексии дают бонус 5–15 XP один раз на запись; за день — не больше 60 XP.
        """
        ref = str(entry_id)
        if is_rewardable_day(day, today) and not self._repo.has_event(owner_id, KIND_ENTRY, ref):
            xp = entry_xp(self._repo.count_events(owner_id, KIND_ENTRY, day))
            self._award(owner_id, KIND_ENTRY, ref, day, xp)
            self._reflect(owner_id, f"entry:{entry_id}", day, marks)
        return self._grant(owner_id, today)

    def award_day_review(
        self, owner_id: int, day: date, today: date, marks: Iterable[str] = ()
    ) -> Progress:
        """Итог дня за `day`: +15 XP один раз за дату (повторное сохранение XP не даёт).

        Отметки рефлексии — бонус один раз за дату: их можно добавить и при повторном сохранении.
        """
        ref = day.isoformat()
        if is_rewardable_day(day, today):
            if not self._repo.has_event(owner_id, KIND_DAY_REVIEW, ref):
                self._award(owner_id, KIND_DAY_REVIEW, ref, day, DAY_REVIEW_XP)
            self._reflect(owner_id, f"review:{ref}", day, marks)
        return self._grant(owner_id, today)

    def record_direction(self, owner_id: int, direction: str, today: date) -> Progress:
        """Разбор по направлению состоялся: нужен достижениям «Исследователя», XP не даёт."""
        self._repo.add_event_once(owner_id, KIND_DIRECTION, direction, today, 0)
        return self._grant(owner_id, today)

    def award_analysis_answer(self, owner_id: int, analysis_id: int, today: date) -> Progress:
        """Ответ на уточняющие вопросы разбора: +10 XP один раз на разбор, длина не важна."""
        ref = str(analysis_id)
        if not self._repo.has_event(owner_id, KIND_ANSWER, ref):
            self._award(owner_id, KIND_ANSWER, ref, today, ANSWER_XP)
        return self._grant(owner_id, today)

    def refresh(self, owner_id: int, today: date) -> Progress:
        """Выдать достижения после действия вне дневника (квест, квиз)."""
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

    def _capped(self, owner_id: int, day: date, xp: int) -> int:
        """Сколько из `xp` помещается в дневной потолок (запись, итог, ответ разбора, рефлексия)."""
        return capped_xp(xp, self._repo.xp_on_day(owner_id, CAPPED_KINDS, day))

    def _award(self, owner_id: int, kind: str, ref: str, day: date, xp: int) -> None:
        """Событие XP под дневным потолком; пишется и при 0 — день и источник учтены."""
        self._repo.add_event_once(owner_id, kind, ref, day, self._capped(owner_id, day, xp))

    def _reflect(self, owner_id: int, ref: str, day: date, marks: Iterable[str]) -> None:
        chosen = clean_marks(marks)
        if chosen and not self._repo.has_event(owner_id, KIND_REFLECTION, ref):
            xp = self._capped(owner_id, day, reflection_bonus(chosen))
            self._repo.add_reflection_once(owner_id, ref, day, xp, ",".join(chosen))

    def _metrics(self, owner_id: int, today: date) -> Metrics:
        rows = self._repo.reflection_marks(owner_id)
        quizzes = {ref.split(":")[0] for ref in self._repo.refs(owner_id, KIND_QUIZ)}
        directions = set(self._repo.refs(owner_id, KIND_DIRECTION))
        return Metrics(
            active_days=frozenset(d for d in self._repo.active_days(owner_id) if d <= today),
            deep_reflections=sum(1 for m in rows if m & DEEP_MARKS),
            gratitude=any("good" in m for m in rows),
            explored=len(quizzes) + len(directions),
            care_steps=self._repo.count_events(owner_id, KIND_QUEST_STEP),
            today=today,
        )

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
            self._repo.add_event_once(owner_id, KIND_WEEKLY_GOAL, ref, today, WEEKLY_GOAL_XP)
        have = [code for code, _ in self._repo.achievements(owner_id)]
        due = earned_achievements(
            entries=self._repo.count_events(owner_id, KIND_ENTRY),
            reviews=self._repo.count_events(owner_id, KIND_DAY_REVIEW),
            streak=streak.current,
            already=have,
        ) + achievements_due(self._metrics(owner_id, today), have)
        for code in due:
            self._repo.add_achievement(owner_id, code, today)
        return self._snapshot(owner_id, today)

    def _snapshot(self, owner_id: int, today: date) -> Progress:
        xp = self._repo.total_xp(owner_id)
        level = level_for(xp)
        earned: list[EarnedAchievement] = []
        stored = self._repo.achievements(owner_id)
        for code, earned_on in stored:
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
        categories, hidden = catalog(self._metrics(owner_id, today), dict(stored))
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
            categories=categories,
            hidden=hidden,
        )
