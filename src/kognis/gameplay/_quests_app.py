"""Сценарии квестов и квизов. Опыт начисляется теми же событиями `xp_events`, что и остальное."""

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kognis.errors import CodedValueError

from ._app import GameplayService
from ._infra import ProgressRepository
from ._quests import (
    KIND_QUEST,
    KIND_QUEST_STEP,
    KIND_QUIZ,
    MAX_TITLE_LENGTH,
    QUEST_STEP_XP,
    QUEST_XP,
    QUESTS,
    QUIZ_XP,
    QUIZZES,
    SOURCE_ANALYSIS,
    SOURCE_LIBRARY,
    TYPE_CHALLENGE,
    TYPE_QUEST,
    AlreadyAcceptedError,
    Quest,
    QuestTemplate,
    QuizAnswers,
    QuizDoneTodayError,
    QuizOutcome,
    QuizStatus,
    StepOutcome,
    StepUnavailableError,
    custom_quest_steps,
    normalize_quiz_answers,
    quiz_by_code,
    template_by_code,
)
from ._quests_infra import NewQuest, QuestRepository, QuizRepository


class QuestService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._quests = QuestRepository(session)
        self._quizzes = QuizRepository(session)
        self._xp = ProgressRepository(session)

    @staticmethod
    def library() -> tuple[QuestTemplate, ...]:
        return QUESTS

    def accept_template(self, owner_id: int, code: str, today: date) -> Quest:
        """Принять квест из библиотеки; тот же квест повторно — после завершения предыдущего."""
        template = template_by_code(code)
        new = NewQuest(
            source=SOURCE_LIBRARY,
            source_ref=template.code,
            template_code=template.code,
            kind=TYPE_CHALLENGE if template.challenge else TYPE_QUEST,
            title=template.title,
            description=template.description,
            steps=template.steps,
        )
        return self._accept(owner_id, new, today)

    def accept_idea(
        self, owner_id: int, analysis_id: int, idea_no: int, idea: str, today: date
    ) -> Quest:
        """Квест из предложения анализа; из одной идеи — один квест."""
        title = idea.strip()
        if not title:
            raise CodedValueError("gameplay.idea_empty")
        new = NewQuest(
            source=SOURCE_ANALYSIS,
            source_ref=f"{analysis_id}:{idea_no}",
            template_code=None,
            kind=TYPE_QUEST,
            title=title[:MAX_TITLE_LENGTH],
            description="Квест по результатам анализа.",
            steps=custom_quest_steps(title),
        )
        return self._accept(owner_id, new, today)

    def quests(self, owner_id: int) -> list[Quest]:
        return self._quests.list_for(owner_id)

    def complete_step(
        self, owner_id: int, quest_id: int, idx: int, today: date
    ) -> StepOutcome | None:
        """Отметить шаг: +15 XP один раз за шаг; последний шаг завершает квест (+50 XP).

        Повторная отметка ничего не меняет и XP не даёт. Шаг челленджа — не чаще одного в день.
        """
        quest = self._quests.get(owner_id, quest_id)
        if quest is None:
            return None
        if not 0 <= idx < len(quest.steps):
            raise CodedValueError("gameplay.step_unknown")
        if quest.steps[idx].done_on is not None:
            return StepOutcome(quest, 0)
        if quest.kind == TYPE_CHALLENGE and any(s.done_on == today for s in quest.steps):
            raise StepUnavailableError("gameplay.step_unavailable")
        try:
            with self._session.begin_nested():
                self._quests.mark_step(quest_id, idx, today)
                xp = self._grant(
                    owner_id, KIND_QUEST_STEP, f"{quest_id}:{idx}", today, QUEST_STEP_XP
                )
                if all(s.done_on is not None or s.idx == idx for s in quest.steps):
                    self._quests.complete(quest_id, today)
                    xp += self._grant(owner_id, KIND_QUEST, str(quest_id), today, QUEST_XP)
        except IntegrityError:
            # параллельная отметка того же шага успела раньше: XP уже начислен ей
            return StepOutcome(self._quests.fetch(quest_id), 0)
        GameplayService(self._session).refresh(owner_id, today)  # «Забота о себе»
        return StepOutcome(self._quests.fetch(quest_id), xp)

    def quiz_statuses(self, owner_id: int, today: date) -> list[QuizStatus]:
        done = self._quizzes.done_codes(owner_id, today)
        return [QuizStatus(q, q.code in done) for q in QUIZZES]

    def quiz_history(self, owner_id: int, code: str) -> list[QuizAnswers]:
        quiz_by_code(code)
        return self._quizzes.history(owner_id, code)

    def submit_quiz(
        self, owner_id: int, code: str, raw_answers: list[str], today: date, *, reward: bool
    ) -> QuizOutcome:
        """Сохранить ответы; +10 XP, не чаще раза в день на квиз (`reward=False` — без XP)."""
        quiz = quiz_by_code(code)
        answers = normalize_quiz_answers(quiz, raw_answers)
        if code in self._quizzes.done_codes(owner_id, today):
            raise QuizDoneTodayError("gameplay.quiz_done_today")
        ref = f"{code}:{today.isoformat()}"
        try:
            with self._session.begin_nested():
                self._quizzes.add(owner_id, code, today, answers)
                xp = self._grant(owner_id, KIND_QUIZ, ref, today, QUIZ_XP) if reward else 0
        except IntegrityError:  # параллельный запрос успел раньше (уникальность держит БД)
            raise QuizDoneTodayError("gameplay.quiz_done_today") from None
        if reward:
            GameplayService(self._session).refresh(owner_id, today)  # «Исследователь»
        return QuizOutcome(xp, QuizAnswers(code, today, answers))

    def _accept(self, owner_id: int, new: NewQuest, today: date) -> Quest:
        if self._quests.has_open(owner_id, new.source, new.source_ref):
            raise AlreadyAcceptedError("gameplay.quest_accepted")
        return self._quests.add_quest(owner_id, new, today)

    def _grant(self, owner_id: int, kind: str, ref: str, today: date, xp: int) -> int:
        """Событие XP; повтор исключён проверками шага и квиза, а в БД — уникальностью."""
        self._xp.add_event(owner_id, kind, ref, today, xp)
        return xp
