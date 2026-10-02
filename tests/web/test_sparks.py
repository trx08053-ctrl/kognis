"""Искры по HTTP (kognis-crn, AC1): начисления, покупка, идемпотентность, конкурентность."""

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import SparkRepository
from kognis.web import create_app

PW = "correct horse"
MON = dt.date(2026, 9, 7)  # понедельник


class Clock:
    def __init__(self, day: dt.date) -> None:
        self.day = day

    def __call__(self) -> dt.datetime:
        return dt.datetime.combine(self.day, dt.time(12), dt.UTC)


@pytest.fixture
def clock() -> Clock:
    return Clock(MON)


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    client = TestClient(create_app(engine, clock=clock))
    assert client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": PW}
    ).is_success
    return client


def entry(client: TestClient, clock: Clock, day: dt.date) -> None:
    clock.day = day
    assert client.post("/api/entries", json={"text": "день", "date": day.isoformat()}).is_success


def buy(client: TestClient, item: str) -> Any:
    return client.post("/api/sparks/purchase", json={"item": item})


def catalog(client: TestClient) -> dict[str, Any]:
    return client.get("/api/sparks").json()


def owned_codes(body: dict[str, Any]) -> set[str]:
    return {item["code"] for item in body["catalog"] if item["owned"]}


def test_catalog_shape(api: TestClient) -> None:
    body = catalog(api)
    assert body["balance"] == 0
    assert body["freezes"] == 2  # стартовый запас заморозок
    codes = {item["code"] for item in body["catalog"]}
    assert {"scarf", "hat", "bg_stars", "bg_forest", "freeze"} <= codes
    assert "theme_slate" not in codes  # темы без эффекта в каталоге нет (TASK kognis-crn, 8)


@pytest.mark.acceptance("kognis-crn", "AC1")
def test_accruals_and_insufficient_balance(api: TestClient, clock: Clock) -> None:
    """Три записи в неделю дают искры (цель и достижения); нехватка — 409 с кодом, без списания."""
    for offset in range(3):
        entry(api, clock, MON + dt.timedelta(days=offset))
    body = catalog(api)
    assert body["balance"] == 40  # недельная цель 20 + first_entry 10 + streak_3 10
    refused = buy(api, "bg_forest")  # стоит 75 — не хватает
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "sparks.not_enough"
    assert catalog(api)["balance"] == 40  # без списания


@pytest.mark.acceptance("kognis-crn", "AC1")
def test_purchase_and_idempotent_repeat(api: TestClient, clock: Clock) -> None:
    """Покупка отмечается купленной и списывает баланс; повторная — 409 без второго списания."""
    for week in range(3):  # три недели по три записи: цель 20/нед + достижения
        for offset in range(3):
            entry(api, clock, MON + dt.timedelta(days=7 * week + offset))
    # 90 = 20×3 недельных цели + first_entry 10 + streak_3 10 + consistency_1 10;
    # streak_7 не выдан: между неделями 4 пропуска, заморозок хватает только на первый
    assert catalog(api)["balance"] == 90
    ok = buy(api, "scarf")
    assert ok.status_code == 200, ok.text
    assert ok.json()["balance"] == 40
    assert owned_codes(ok.json()) == {"scarf"}
    repeat = buy(api, "scarf")  # тот же товар навсегда один
    assert repeat.status_code == 409
    assert repeat.json()["detail"]["code"] == "sparks.owned"
    assert catalog(api)["balance"] == 40  # повторная покупка не списывает дважды


def test_unknown_item_is_422(api: TestClient) -> None:
    r = buy(api, "no_such_item")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "sparks.item_unknown"


def test_freeze_purchase_refused_when_stock_full(api: TestClient, clock: Clock) -> None:
    """Заморозка при полном запасе (2) не продаётся: без вины, но и без пустой траты искр."""
    entry(api, clock, MON)
    r = buy(api, "freeze")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "sparks.freeze_full"


def test_concurrent_purchases_never_go_negative(engine: Engine, clock: Clock) -> None:
    """Параллельные покупки при балансе на одну: минуса не возникает ни в каком исходе."""
    client = TestClient(create_app(engine, clock=clock))
    assert client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": PW}
    ).is_success
    with transaction(engine) as session:
        SparkRepository(session).add_spark_once(1, "weekly_goal", "2026-W37", MON, 100)

    def purchase(item: str) -> Any:
        client = TestClient(create_app(engine, clock=clock))
        assert client.post(
            "/api/auth/login", json={"email": "a@example.com", "password": PW}
        ).is_success
        return buy(client, item)

    codes = ["scarf", "hat", "backpack"]  # по 50: хватит максимум на две
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(purchase, codes))
    successes = sum(1 for r in results if r.status_code == 200)
    body = catalog(client)
    assert body["balance"] >= 0  # минуса нет ни в каком исходе
    assert len(owned_codes(body)) == successes  # успешных — ровно столько, сколько куплено
    assert 50 * successes + body["balance"] == 100  # искры не появились из ниоткуда
