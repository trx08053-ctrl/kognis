"""Модуль gameplay: опыт, уровни, серия, достижения, квесты, квизы (D8)."""

from ._app import GameplayService, RecoveryUnavailableError
from ._domain import ACHIEVEMENTS, AchievementDef, EarnedAchievement, Progress, RecoveryOffer
from ._heroes import APPEARANCES, HeroLine, Postcard
from ._heroes_app import CompanionState, HeroService, MentorState
from ._quests import (
    AlreadyAcceptedError,
    Quest,
    QuestStep,
    QuestTemplate,
    QuizAnswers,
    QuizDef,
    QuizDoneTodayError,
    QuizOutcome,
    QuizStatus,
    StepOutcome,
    StepUnavailableError,
)
from ._quests_app import QuestService
from ._sparks import (
    ACHIEVEMENT_SPARKS,
    SHOP,
    SPARK_QUEST,
    SPARK_WEEKLY_GOAL,
    ShopItem,
    achievement_sparks,
    item_by_code,
    purchase_ref,
)
from ._sparks_app import (
    FreezeStockFullError,
    ShopPosition,
    SparksService,
    SparksState,
)
from ._sparks_infra import NotEnoughSparksError, OwnedItemError, SparkRepository

__all__ = [
    "ACHIEVEMENTS",
    "ACHIEVEMENT_SPARKS",
    "APPEARANCES",
    "SHOP",
    "SPARK_QUEST",
    "SPARK_WEEKLY_GOAL",
    "AchievementDef",
    "AlreadyAcceptedError",
    "CompanionState",
    "EarnedAchievement",
    "FreezeStockFullError",
    "GameplayService",
    "HeroLine",
    "HeroService",
    "MentorState",
    "NotEnoughSparksError",
    "OwnedItemError",
    "Postcard",
    "Progress",
    "Quest",
    "QuestService",
    "QuestStep",
    "QuestTemplate",
    "QuizAnswers",
    "QuizDef",
    "QuizDoneTodayError",
    "QuizOutcome",
    "QuizStatus",
    "RecoveryOffer",
    "RecoveryUnavailableError",
    "ShopItem",
    "ShopPosition",
    "SparkRepository",
    "SparksService",
    "SparksState",
    "StepOutcome",
    "StepUnavailableError",
    "achievement_sparks",
    "item_by_code",
    "purchase_ref",
]
