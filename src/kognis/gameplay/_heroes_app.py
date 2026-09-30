"""Сценарии героев: спутник (стадия, открытка, реплика) и наставники. Вызывает слой web (D2)."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ._app import GameplayService
from ._domain import KIND_DIRECTION
from ._heroes import (
    MENTORS,
    HeroLine,
    LineContext,
    Postcard,
    choose_line,
    companion_stage,
    days_to_next_stage,
    is_resting,
    pick_postcard,
    unlocked_mentors,
    validate_companion,
)
from ._heroes_infra import CompanionRow, HeroRepository
from ._infra import ProgressRepository
from ._quests import template_by_code
from ._quests_infra import QuestRepository
from ._streak import days_with_diary


@dataclass(frozen=True)
class MentorState:
    code: str
    direction: str
    unlocked: bool


@dataclass(frozen=True)
class CompanionState:
    chosen: bool
    appearance: str | None
    name: str | None
    address: str | None
    stage: int
    days_total: int
    days_to_next: int | None
    resting: bool
    line: HeroLine | None
    postcard: Postcard | None
    mentors: tuple[MentorState, ...]


class HeroService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = HeroRepository(session)
        self._xp = ProgressRepository(session)

    def state(self, owner_id: int, today: date) -> CompanionState:
        """Состояние героев. Заодно приносит открытку дня — один раз в день (идемпотентно)."""
        companion = self._repo.companion(owner_id)
        days = [d for d in self._xp.active_days(owner_id) if d <= today]
        _, days_total = days_with_diary(days, today)
        stage = companion_stage(days_total)
        last_active = max(days) if days else None
        opened = self._unlocked(owner_id)
        mentors = tuple(MentorState(m.code, m.direction, m.code in opened) for m in MENTORS)
        if companion is None:
            return CompanionState(
                False, None, None, None, stage, days_total, days_to_next_stage(days_total),
                False, HeroLine("companion", "intro"), None, mentors,
            )  # fmt: skip
        postcard = self._postcard(owner_id, today)
        line = choose_line(
            LineContext(
                stage=stage,
                stage_seen=companion.stage_seen,
                last_active=last_active,
                reviewed_today=self._repo.has_review_on(owner_id, today),
                active_today=today in days,
                streak=GameplayService(self._session).progress(owner_id, today).streak,
                today=today,
            )
        )
        return CompanionState(
            True,
            companion.appearance,
            companion.name,
            companion.address,
            stage,
            days_total,
            days_to_next_stage(days_total),
            is_resting(last_active, today),
            line,
            postcard,
            mentors,
        )

    def choose(
        self, owner_id: int, appearance: str, name: str, address: str, today: date
    ) -> CompanionState:
        """Выбор облика, имени и обращения (знакомство) или их смена."""
        clean = validate_companion(appearance, name, address)
        days = [d for d in self._xp.active_days(owner_id) if d <= today]
        stage = companion_stage(days_with_diary(days, today)[1])
        self._repo.save_companion(owner_id, CompanionRow(appearance, clean, address, stage), today)
        return self.state(owner_id, today)

    def mark_stage_seen(self, owner_id: int, today: date) -> CompanionState:
        """Пользователь увидел реплику о новой стадии — больше её не показываем."""
        days = [d for d in self._xp.active_days(owner_id) if d <= today]
        self._repo.mark_stage_seen(owner_id, companion_stage(days_with_diary(days, today)[1]))
        return self.state(owner_id, today)

    def _postcard(self, owner_id: int, today: date) -> Postcard | None:
        """После итога дня спутник уходит в путешествие и к следующему дню приносит открытку."""
        card = self._repo.postcard_on(owner_id, today)
        if card is not None:
            return card
        review = self._repo.latest_review_before(owner_id, today)
        if review is None:
            return None
        delivered = self._repo.latest_postcard_for_day(owner_id)
        if delivered is not None and delivered >= review:
            return None
        self._repo.add_postcard_once(owner_id, today, review, pick_postcard(owner_id, today))
        return self._repo.postcard_on(owner_id, today)

    def _unlocked(self, owner_id: int) -> list[str]:
        """Наставник открыт разбором своего направления или квестом библиотеки этого направления."""
        directions = set(self._xp.refs(owner_id, KIND_DIRECTION))
        for quest in QuestRepository(self._session).list_for(owner_id):
            if quest.template_code:
                directions.add(template_by_code(quest.template_code).direction)
        return unlocked_mentors(directions)
