"""Цифровые герои: приёмочный e2e kognis-zjg (AC5) — скриншоты и axe в светлой и тёмной теме."""

import importlib
import json
import socket
import threading
import time
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, cast

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, expect, sync_playwright
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

Axe: Any = importlib.import_module("axe_playwright_python.sync_playwright").Axe

ROOT = Path(__file__).resolve().parents[2]
SCREENS = ROOT / ".evidence" / "screens"
VALID_PW = "correct horse"


class Calm:
    """Ответ модели без паттернов: достаточно, чтобы разбор состоялся и открыл наставника."""

    def complete(self, system: str, messages: Sequence[Message], schema: object = None) -> str:
        body: dict[str, Any] = {
            "summary": "Неделя прошла спокойно.",
            "patterns": [],
            "questions": [],
            "quest_ideas": [],
        }
        return json.dumps(body)


@contextmanager
def serve(app: FastAPI) -> Generator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
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
        try:
            b = p.chromium.launch()
        except Exception as err:
            pytest.fail(f"нет браузера для e2e — выполните `just setup-browsers` ({err})")
        yield b
        b.close()


def check_axe(page: Page) -> None:
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [
        f"{v['id']}: {v['help']} {[n['target'] for n in v.get('nodes', [])][:5]}" for v in serious
    ]


@pytest.mark.acceptance("kognis-zjg", "AC5")
@pytest.mark.e2e
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_heroes_screenshots_and_axe(
    browser: Browser, engine: Engine, scheme: Literal["light", "dark"]
) -> None:
    """Знакомство со спутником и наставник в разборе: без serious/critical нарушений axe."""
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    SCREENS.mkdir(parents=True, exist_ok=True)
    with serve(create_app(engine, ai_provider=Calm())) as url:
        context = browser.new_context(locale="ru-RU", color_scheme=scheme)
        page = context.new_page()
        page.goto(url)
        page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
        page.get_by_label("Email").fill("heroes@example.com")
        page.get_by_label("Пароль").fill(VALID_PW)
        page.get_by_test_id("auth-submit").click()
        expect(page.get_by_test_id("companion-intro")).to_be_visible()
        page.get_by_label("Имя").fill("Луна")
        page.get_by_role("button", name="Познакомиться").click()
        expect(page.get_by_test_id("companion-art")).to_be_visible()
        page.screenshot(path=str(SCREENS / f"e2e-heroes-companion-{scheme}.png"), full_page=True)
        check_axe(page)

        page.get_by_label("Что произошло и что вы чувствуете").fill("Сегодня спокойный день")
        page.get_by_test_id("save-entry").click()
        expect(page.get_by_test_id("entries")).to_contain_text("спокойный день")
        page.get_by_role("link", name="Разбор").click()
        page.get_by_label("Согласен(на) передать записи").check()
        page.get_by_test_id("run-analysis").click()
        expect(page.get_by_test_id("analysis-result")).to_be_visible()
        expect(page.get_by_test_id("mentor-line")).to_contain_text("Аналитик")
        page.screenshot(path=str(SCREENS / f"e2e-heroes-mentor-{scheme}.png"), full_page=True)
        check_axe(page)
        context.close()
