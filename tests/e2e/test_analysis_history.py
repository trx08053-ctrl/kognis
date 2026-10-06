"""История разборов: приёмочный e2e kognis-qkh (AC1) — разбор не теряется при уходе со страницы."""

import json
import socket
import threading
import time
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, expect, sync_playwright
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

ROOT = Path(__file__).resolve().parents[2]
VALID_PW = "correct horse"


class OnePattern:
    """Ответ модели с одним паттерном, опирающимся на запись №1."""

    def complete(self, system: str, messages: Sequence[Message], schema: object = None) -> str:
        return json.dumps(
            {
                "summary": "Неделя прошла напряжённо.",
                "patterns": [
                    {
                        "title": "Избегание",
                        "description": "Неприятные задачи откладываются.",
                        "entry_ids": [1],
                        "quotes": ["страшно звонить"],
                    }
                ],
                "questions": ["Что помогло бы начать?"],
                "quest_ideas": [],
            }
        )


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


@pytest.fixture
def page(browser: Browser, engine: Engine) -> Iterator[Page]:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    with serve(create_app(engine, ai_provider=OnePattern())) as url:
        context = browser.new_context(locale="ru-RU")
        page = context.new_page()
        page.goto(url)
        yield page
        context.close()


@pytest.mark.acceptance("kognis-qkh", "AC1")
@pytest.mark.e2e
def test_analysis_survives_leaving_the_page_and_can_be_deleted(page: Page) -> None:
    page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
    page.get_by_label("Email").fill("history@example.com")
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    page.get_by_test_id("user-menu").click()
    expect(page.get_by_test_id("whoami")).to_have_text("history@example.com")
    page.keyboard.press("Escape")
    page.get_by_label("Что произошло и что вы чувствуете").fill("Сегодня страшно звонить")
    page.get_by_test_id("save-entry").click()
    expect(page.get_by_test_id("entries")).to_contain_text("страшно звонить")

    page.get_by_role("link", name="Разбор").click()
    expect(page.get_by_text("Пока нет сохранённых разборов.")).to_be_visible()
    page.get_by_label("Согласен(на) передать записи").check()
    page.get_by_test_id("run-analysis").click()
    expect(page.get_by_test_id("analysis-result")).to_contain_text("Избегание")
    expect(page.get_by_test_id("analysis-history-item")).to_have_count(1)

    page.get_by_role("link", name="Дневник").click()
    expect(page.get_by_test_id("analysis-result")).to_have_count(0)
    page.get_by_role("link", name="Разбор").click()
    expect(page.get_by_test_id("analysis-result")).to_contain_text("Избегание")
    expect(page.get_by_test_id("analysis-result")).to_contain_text("страшно звонить")

    page.reload()
    expect(page.get_by_test_id("analysis-result")).to_contain_text("Избегание")

    page.get_by_role("button", name="Удалить разбор", exact=False).click()
    page.get_by_role("button", name="Да, удалить").click()
    expect(page.get_by_text("Пока нет сохранённых разборов.")).to_be_visible()
    expect(page.get_by_test_id("analysis-result")).to_have_count(0)
