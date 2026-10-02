"""Искры (kognis-crn, AC1 — часть про начисления): журнал, идемпотентность, баланс.

Начисления — за проверяемые факты (недельная цель, уровень достижения, квест), не за объём.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import (
    SHOP,
    SPARK_QUEST,
    SPARK_WEEKLY_GOAL,
    GameplayService,
    NotEnoughSparksError,
    OwnedItemError,
    QuestService,
    SparkRepository,
    achievement_sparks,
    item_by_code,
    purchase_ref,
)
from kognis.gameplay._sparks import COSMETIC_ONCE, ITEM_FREEZE

MON = date(2026, 9, 7)  # понедельник
TUE, WED, THU = MON + timedelta(days=1), MON + timedelta(days=2), MON + timedelta(days=3)


def test_achievement_sparks_by_level_and_old_codes_as_bronze() -> None:
    assert achievement_sparks("consistency_1") == 10
    assert achievement_sparks("depth_2") == 25
    assert achievement_sparks("explorer_3") == 50
    assert achievement_sparks("first_entry") == 10  # старые коды — как бронза
    assert achievement_sparks("streak_30") == 10


def test_shop_catalog_invariants() -> None:
    codes = [item.code for item in SHOP]
    assert len(codes) == len(set(codes))  # коды уникальны
    assert all(item.price > 0 for item in SHOP)
    assert sum(1 for item in SHOP if item.kind == ITEM_FREEZE) == 1  # заморозка одна
    with pytest.raises(KeyError):
        item_by_code("unknown")


def test_purchase_ref_cosmetic_once_and_freeze_per_week() -> None:
    scarf = item_by_code("scarf")
    freeze = item_by_code("freeze")
    assert purchase_ref(scarf, MON) == COSMETIC_ONCE
    assert purchase_ref(freeze, MON) == "2026-W37"
    assert purchase_ref(freeze, WED) == "2026-W37"  # одна ISO-неделя — один ref


def test_weekly_goal_grants_sparks_once(engine: Engine) -> None:
    """Три записи в неделю закрывают цель 3: +20 искров за неделю, не больше."""
    with transaction(engine) as session:
        service = GameplayService(session)
        service.save_settings(1, [], 3, MON)
        for n, day in enumerate((MON, TUE, WED)):
            service.award_entry(1, 100 + n, day, day)
        # first_entry (+10) за первую запись и streak_3 (+10) за три дня подряд — как бронза
        expected = (
            SPARK_WEEKLY_GOAL + achievement_sparks("first_entry") + achievement_sparks("streak_3")
        )
        assert SparkRepository(session).balance(1) == expected
        service.award_entry(1, 200, THU, THU)  # четвёртый день недели — ещё раз не начисляется
        assert SparkRepository(session).balance(1) == expected


def test_first_entry_achievement_grants_bronze_sparks(engine: Engine) -> None:
    """Первая запись: достижение first_entry — искры как за бронзу, один раз."""
    with transaction(engine) as session:
        GameplayService(session).award_entry(1, 10, MON, MON)
        assert SparkRepository(session).balance(1) == 10
        GameplayService(session).award_entry(1, 11, TUE, TUE)  # достижение уже выдано
        assert SparkRepository(session).earned(1) == 10


def test_completed_quest_grants_sparks_once(engine: Engine) -> None:
    """Завершённый квест: +15 искров; повторные отметки шагов больше не начисляют."""
    with transaction(engine) as session:
        quest = QuestService(session).accept_template(1, "strengths", MON)
        outcome = QuestService(session).complete_step(1, quest.id, 0, MON)
        assert outcome is not None
        assert SparkRepository(session).balance(1) == 0  # квест не завершён
        for idx in range(1, 3):
            QuestService(session).complete_step(1, quest.id, idx, TUE)
        assert SparkRepository(session).balance(1) == SPARK_QUEST
        QuestService(session).complete_step(1, quest.id, 2, WED)  # повторный шаг
        assert SparkRepository(session).balance(1) == SPARK_QUEST


def test_purchase_requires_balance_and_is_idempotent(engine: Engine) -> None:
    """Недостаток — ошибка без списания; уже купленное не списывает повторно."""
    scarf = item_by_code("scarf")
    with transaction(engine) as session:
        repo = SparkRepository(session)
        with pytest.raises(NotEnoughSparksError):
            repo.add_purchase(1, scarf.code, purchase_ref(scarf, MON), scarf.price, MON)
        assert repo.balance(1) == 0  # без списания
        repo.add_spark_once(1, "weekly_goal", "2026-W37", MON, 60)
        repo.add_purchase(1, scarf.code, purchase_ref(scarf, MON), scarf.price, MON)
        assert repo.balance(1) == 10
        with pytest.raises(OwnedItemError):  # тот же товар с тем же ref
            repo.add_purchase(1, scarf.code, purchase_ref(scarf, MON), scarf.price, TUE)
        assert repo.balance(1) == 10  # повторная покупка не списывает


def test_sparks_are_per_user(engine: Engine) -> None:
    with transaction(engine) as session:
        repo = SparkRepository(session)
        repo.add_spark_once(1, "weekly_goal", "2026-W37", MON, 20)
        assert repo.balance(1) == 20
        assert repo.balance(2) == 0
        assert repo.purchases(2) == []


def test_parallel_purchase_hitting_unique_is_owned_not_a_charge(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Параллельная покупка успела записаться раньше проверки владения:
    конфликт уникальности — «уже куплено», без второго списания."""

    def always_new(_self: SparkRepository, *_args: object) -> bool:
        return False

    scarf = item_by_code("scarf")
    with transaction(engine) as session:
        repo = SparkRepository(session)
        repo.add_spark_once(1, "weekly_goal", "2026-W37", MON, 100)
        repo.add_purchase(1, scarf.code, purchase_ref(scarf, MON), scarf.price, MON)
        monkeypatch.setattr(SparkRepository, "has_purchase", always_new)
        with pytest.raises(OwnedItemError):
            repo.add_purchase(1, scarf.code, purchase_ref(scarf, MON), scarf.price, TUE)
        monkeypatch.undo()
        assert repo.balance(1) == 50  # списание одно
