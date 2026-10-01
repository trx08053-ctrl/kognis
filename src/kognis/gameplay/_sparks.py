"""Искры (мотивация 2.0, 4/4): валюта за регулярность, траты только на косметику.

Без ввода-вывода. Правила — данные. Принципы ADR 0006: валюта не продаёт прогресс, разборы
и аналитику; начисления — за проверяемые факты (недельная цель, уровень достижения,
завершённый квест), не за объём и тон записей. Баланс не бывает отрицательным.
"""

from dataclasses import dataclass
from datetime import date

from ._achievements import CATEGORY_TARGETS
from ._streak import week_ref

SPARK_WEEKLY_GOAL = 20  # недельная цель по дням с дневником
SPARK_QUEST = 15  # завершённый квест
ACHIEVEMENT_SPARKS = {1: 10, 2: 25, 3: 50}  # уровень достижения (bronze/silver/gold)

# источник события искр в журнале: уникальность (owner, kind, ref) исключает двойное начисление
KIND_SPARK_WEEKLY_GOAL = "weekly_goal"
KIND_SPARK_ACHIEVEMENT = "achievement"
KIND_SPARK_QUEST = "quest"

# товары: косметика спутника и дневника, дополнительная заморозка серии
ITEM_ACCESSORY = "accessory"
ITEM_BACKGROUND = "background"
ITEM_THEME = "theme"
ITEM_FREEZE = "freeze"

COSMETIC_ONCE = "once"  # ref косметики: покупается один раз навсегда
FREEZE_WEEKS_LIMIT = 1  # заморозка — не чаще одной покупки в ISO-неделю


@dataclass(frozen=True)
class ShopItem:
    code: str
    kind: str
    price: int


SHOP: tuple[ShopItem, ...] = (
    ShopItem("scarf", ITEM_ACCESSORY, 50),
    ShopItem("hat", ITEM_ACCESSORY, 50),
    ShopItem("backpack", ITEM_ACCESSORY, 50),
    ShopItem("bg_stars", ITEM_BACKGROUND, 75),
    ShopItem("bg_forest", ITEM_BACKGROUND, 75),
    ShopItem("theme_slate", ITEM_THEME, 100),
    ShopItem("freeze", ITEM_FREEZE, 30),
)


def item_by_code(code: str) -> ShopItem:
    for item in SHOP:
        if item.code == code:
            return item
    raise KeyError(code)


def achievement_sparks(code: str) -> int:
    """Искры за выданное достижение: уровень — у новых кодов `<категория>_<уровень>`,
    старые коды (`first_entry`, `streak_3`, `reviews_10`) — как бронза."""
    prefix, _, suffix = code.rpartition("_")
    if prefix in CATEGORY_TARGETS and suffix.isdigit() and int(suffix) in ACHIEVEMENT_SPARKS:
        return ACHIEVEMENT_SPARKS[int(suffix)]
    return ACHIEVEMENT_SPARKS[1]


def purchase_ref(item: ShopItem, today: date) -> str:
    """Идентификатор покупки: косметика навсегда одна, заморозка — по одной в ISO-неделю."""
    return COSMETIC_ONCE if item.kind != ITEM_FREEZE else week_ref(today)
