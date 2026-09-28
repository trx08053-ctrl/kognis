"""Квесты, челленджи и квизы-рефлексии (D8): библиотека — данные, правила без ввода-вывода."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

QUEST_STEP_XP = 15
QUEST_XP = 50
QUIZ_XP = 10

KIND_QUEST_STEP = "quest_step"
KIND_QUEST = "quest"
KIND_QUIZ = "quiz"

SOURCE_LIBRARY = "library"
SOURCE_ANALYSIS = "analysis"
TYPE_QUEST = "quest"
TYPE_CHALLENGE = "challenge"

MAX_TITLE_LENGTH = 200
MAX_ANSWER_LENGTH = 2_000


@dataclass(frozen=True)
class QuestTemplate:
    code: str
    title: str
    description: str
    direction: str  # код направления анализа (см. analysis.DIRECTIONS), только для подписи
    steps: tuple[str, ...]
    challenge: bool = False


def _challenge(
    code: str, title: str, description: str, direction: str, prompts: Sequence[str]
) -> QuestTemplate:
    steps = tuple(f"День {n}: {prompt}" for n, prompt in enumerate(prompts, start=1))
    return QuestTemplate(code, title, description, direction, steps, challenge=True)


QUESTS: tuple[QuestTemplate, ...] = (
    QuestTemplate(
        "catch_thought",
        "Поймай автоматическую мысль",
        "Учимся замечать мысль между событием и эмоцией.",
        "cbt",
        (
            "Вспомни ситуацию, после которой настроение просело",
            "Запиши мысль, которая пришла первой",
            "Найди в ней факты «за» и «против»",
            "Сформулируй более взвешенную мысль",
        ),
    ),
    QuestTemplate(
        "values_in_action",
        "Ценности в действии",
        "Выбираем важное и делаем один маленький шаг в его сторону.",
        "act",
        (
            "Назови одну ценность, которая тебе сейчас важна",
            "Придумай действие на 10 минут в её русле",
            "Выполни его",
            "Запиши, что ты почувствовал(а)",
        ),
    ),
    QuestTemplate(
        "inner_critic",
        "Знакомство с внутренним критиком",
        "Замечаем повторяющийся строгий голос и отвечаем ему по-доброму.",
        "schema",
        (
            "Запиши фразу, которой критик обычно тебя отчитывает",
            "Отметь, в каких ситуациях он появляется",
            "Ответь ему так, как ответил(а) бы близкому другу",
        ),
    ),
    QuestTemplate(
        "strengths",
        "Мои сильные стороны",
        "Собираем ресурсы, на которые можно опереться.",
        "positive",
        (
            "Вспомни трудную ситуацию, с которой ты справился(лась)",
            "Назови, какие качества тебе помогли",
            "Придумай, где применить их на этой неделе",
        ),
    ),
    _challenge(
        "gratitude_7",
        "7 дней благодарности",
        "Один шаг в день: замечать хорошее.",
        "positive",
        (
            "запиши одну вещь, за которую благодарен(на)",
            "поблагодари кого-то лично или сообщением",
            "заметь приятную мелочь в течение дня",
            "вспомни, что помогло тебе в трудный момент",
            "запиши то, что сегодня получилось",
            "назови человека, который тебя поддерживает",
            "перечитай свои записи и отметь, что изменилось",
        ),
    ),
    _challenge(
        "activation_5",
        "5 дней активности",
        "Маленькие приятные и значимые дела, по одному в день.",
        "activation",
        (
            "выйди на 10-минутную прогулку",
            "сделай одно дело, которое давно откладывал(а)",
            "займись чем-то приятным 15 минут",
            "напиши или позвони близкому человеку",
            "выбери занятие на выходные и запланируй его",
        ),
    ),
)


@dataclass(frozen=True)
class QuizDef:
    code: str
    title: str
    questions: tuple[str, ...]


QUIZZES: tuple[QuizDef, ...] = (
    QuizDef(
        "evening",
        "Вечерняя рефлексия",
        (
            "Что сегодня было самым важным?",
            "Что удалось лучше, чем ожидалось?",
            "Что бы ты сделал(а) иначе?",
        ),
    ),
    QuizDef(
        "thoughts",
        "Мысли и факты",
        (
            "Какая мысль сегодня повторялась чаще всего?",
            "Какие факты её подтверждают, а какие — нет?",
            "Как бы ты посмотрел(а) на это через год?",
        ),
    ),
    QuizDef(
        "values",
        "Ценности дня",
        (
            "Что из сделанного сегодня отражает то, что тебе важно?",
            "Какое одно маленькое действие приблизит тебя к важному завтра?",
        ),
    ),
)


def template_by_code(code: str) -> QuestTemplate:
    for template in QUESTS:
        if template.code == code:
            return template
    raise ValueError("неизвестный квест")


def quiz_by_code(code: str) -> QuizDef:
    for quiz in QUIZZES:
        if quiz.code == code:
            return quiz
    raise ValueError("неизвестный квиз")


def custom_quest_steps(idea: str) -> tuple[str, ...]:
    """Квест из предложения анализа: идея становится серединой из трёх маленьких шагов."""
    return (
        "Уточни, что именно и когда ты сделаешь",
        idea,
        "Отметь, как это повлияло на настроение",
    )


def normalize_quiz_answers(quiz: QuizDef, raw: Sequence[str]) -> tuple[str, ...]:
    """Ответы — по одному на вопрос, каждый непустой."""
    answers = tuple(a.strip() for a in raw)
    if len(answers) != len(quiz.questions) or not all(answers):
        raise ValueError("нужен непустой ответ на каждый вопрос")
    if any(len(a) > MAX_ANSWER_LENGTH for a in answers):
        raise ValueError("ответ слишком длинный")
    return answers


class AlreadyAcceptedError(Exception):
    """Такой квест уже принят и не завершён."""


class StepUnavailableError(Exception):
    """Шаг сейчас отметить нельзя (например, второй шаг челленджа за день)."""


class QuizDoneTodayError(Exception):
    """Квиз уже пройден сегодня."""


@dataclass(frozen=True)
class QuestStep:
    idx: int
    title: str
    done_on: date | None


@dataclass(frozen=True)
class Quest:
    id: int
    source: str
    template_code: str | None
    kind: str
    title: str
    description: str
    created_on: date
    completed_on: date | None
    steps: tuple[QuestStep, ...]


@dataclass(frozen=True)
class StepOutcome:
    quest: Quest
    xp: int  # начислено этой отметкой (шаг + завершение квеста)


@dataclass(frozen=True)
class QuizStatus:
    quiz: QuizDef
    done_today: bool


@dataclass(frozen=True)
class QuizAnswers:
    quiz_code: str
    day: date
    answers: tuple[str, ...]


@dataclass(frozen=True)
class QuizOutcome:
    xp: int
    answers: QuizAnswers
