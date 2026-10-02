"""Искры: приёмочный e2e kognis-crn (AC4) — покупка аксессуара меняет облик спутника."""

import importlib
import socket
import threading
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.engine import Engine
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer

from kognis.db import transaction
from kognis.gameplay import SparkRepository
from kognis.web import create_app

Axe: Any = importlib.import_module("axe_playwright_python.sync_playwright").Axe

ROOT = Path(__file__).resolve().parents[2]
SCREENS = ROOT / ".evidence" / "screens"
VALID_PW = "correct horse"
EMAIL = "sparks@example.com"


@contextmanager
def serve(engine: Engine) -> Generator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = UvicornServer(UvicornConfig(create_app(engine), port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        yield p.chromium.launch()


def check_axe(page: Page) -> None:
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [
        f"{v['id']}: {v['help']} {[n['target'] for n in v.get('nodes', [])][:5]}" for v in serious
    ]


def seed_sparks(engine: Engine, owner_id: int) -> None:
    """Arrange: стартовый баланс, чтобы покупка не требовала недель записей."""
    with transaction(engine) as session:
        SparkRepository(session).add_spark_once(
            owner_id, "weekly_goal", "seed", date(2026, 9, 1), 100
        )


@pytest.mark.acceptance("kognis-crn", "AC4")
@pytest.mark.e2e
def test_accessory_purchase_changes_companion(browser: Browser, engine: Engine) -> None:
    """Магазин на профиле: покупка шарфа рисует аксессуар на спутнике (скриншот, axe)."""
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    SCREENS.mkdir(parents=True, exist_ok=True)
    with serve(engine) as url:
        page = browser.new_context(locale="ru-RU").new_page()
        page.goto(url)
        page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
        page.get_by_label("Email").fill(EMAIL)
        page.get_by_label("Пароль").fill(VALID_PW)
        page.get_by_test_id("auth-submit").click()
        expect(page.get_by_test_id("companion-intro")).to_be_visible()
        page.get_by_label("Имя").fill("Луна")
        page.get_by_role("button", name="Познакомиться").click()
        expect(page.get_by_test_id("companion-art")).to_be_visible()

        with engine.connect() as conn:
            owner_id = conn.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": EMAIL}
            ).scalar_one()
        seed_sparks(engine, owner_id)

        page.get_by_role("link", name="Профиль").click()
        expect(page.get_by_test_id("sparks")).to_be_visible()
        expect(page.get_by_test_id("sparks-balance")).to_contain_text("100")
        page.get_by_role("button", name="Купить").first.click()
        expect(page.get_by_test_id("shop-scarf-owned")).to_be_visible()

        page.get_by_role("link", name="Дневник").click()
        expect(page.get_by_test_id("companion-art")).to_be_visible()
        expect(page.get_by_test_id("companion-art")).to_have_attribute("data-accessory", "scarf")
        page.screenshot(path=str(SCREENS / "e2e-sparks-accessory.png"), full_page=True)
        check_axe(page)
        page.close()
