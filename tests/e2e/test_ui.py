"""Сквозной сценарий в браузере (Playwright): регистрация, запись, новый сеанс, изоляция, a11y.

Скриншоты — в .evidence/screens/ (агент может открыть их и посмотреть на интерфейс).
"""

import importlib
import json
import socket
import threading
import time
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, expect, sync_playwright
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

# axe-playwright-python без аннотаций типов — загружаем как Any, результат проверяем явно
Axe: Any = importlib.import_module("axe_playwright_python.sync_playwright").Axe

ROOT = Path(__file__).resolve().parents[2]
SCREENS = ROOT / ".evidence" / "screens"
VALID_PW = "correct horse"


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as err:
            pytest.fail(f"нет браузера для e2e — выполните `just setup-browsers` ({err})")
        yield b
        b.close()


def fresh_page(browser: Browser, url: str) -> Page:
    """Новый контекст = новый сеанс браузера без cookie."""
    frontend = ROOT / "frontend"
    if (frontend / "package.json").exists() and not (frontend / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    page = browser.new_context(viewport={"width": 1024, "height": 700}).new_page()
    page.goto(url)
    return page


@pytest.fixture
def page(browser: Browser, live_server: str) -> Iterator[Page]:
    page = fresh_page(browser, live_server)
    yield page
    page.context.close()


def register(page: Page, email: str) -> None:
    page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
    page.get_by_label("Email").fill(email)
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    expect(page.get_by_test_id("whoami")).to_have_text(email)


def login(page: Page, email: str) -> None:
    page.get_by_label("Email").fill(email)
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    expect(page.get_by_test_id("whoami")).to_have_text(email)


@pytest.mark.acceptance("kognis-b8z", "AC2")
@pytest.mark.e2e
def test_u1_entry_survives_new_session_and_is_private(
    browser: Browser, live_server: str, page: Page
) -> None:
    """Регистрация → запись → новый сеанс браузера после входа видит запись;
    второй пользователь не видит чужую запись ни в интерфейсе, ни через API (R1)."""
    register(page, "ann@example.com")
    page.get_by_label("Что произошло и что вы чувствуете").fill("Сегодня было тревожно")
    page.get_by_label("Теги (через запятую)").fill("Работа, сон")
    page.get_by_label("Эмоции (через запятую)").fill("тревога")
    page.get_by_test_id("save-entry").click()
    expect(page.get_by_test_id("entries")).to_contain_text("Сегодня было тревожно")
    expect(page.get_by_test_id("entries")).to_contain_text("#работа")
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-diary.png"), full_page=True)

    # новый сеанс: без cookie — форма входа; после входа запись на месте
    second = fresh_page(browser, live_server)
    expect(second.get_by_role("heading", name="Вход")).to_be_visible()
    login(second, "ann@example.com")
    expect(second.get_by_test_id("entries")).to_contain_text("Сегодня было тревожно")
    entry_id = second.context.request.get(f"{live_server}/api/entries").json()[0]["id"]
    second.context.close()

    # другой пользователь: пусто в интерфейсе, 404 по API
    other = fresh_page(browser, live_server)
    register(other, "bob@example.com")
    expect(other.get_by_text("Пока нет записей.")).to_be_visible()
    expect(other.get_by_text("Сегодня было тревожно")).to_have_count(0)
    assert other.context.request.get(f"{live_server}/api/entries/{entry_id}").status == 404
    other.context.close()


@pytest.mark.e2e
def test_wrong_password_shows_error(page: Page) -> None:
    page.get_by_label("Email").fill("nobody@example.com")
    page.get_by_label("Пароль").fill("wrong password")
    page.get_by_test_id("auth-submit").click()
    expect(page.get_by_role("alert")).to_contain_text("неверный")


@pytest.mark.e2e
def test_day_review_saved_error_shown_and_history_private(
    browser: Browser, live_server: str, page: Page
) -> None:
    """Итог дня в браузере: значение вне 1–10 → понятная ошибка; исправление → итог в истории;
    повторное сохранение за ту же дату не плодит записи; другой пользователь истории не видит."""
    register(page, "ann@example.com")
    page.get_by_role("link", name="Итог дня").click()
    page.get_by_label("Самочувствие (1–10)").fill("11")
    page.get_by_test_id("save-review").click()
    expect(page.get_by_role("alert")).to_contain_text("от 1 до 10")

    page.get_by_label("Самочувствие (1–10)").fill("4")
    page.get_by_label("Настроение (1–10)").fill("7")
    page.get_by_label("Рефлексия: что запомнилось сегодня").fill("Прогулка помогла")
    page.get_by_test_id("save-review").click()
    expect(page.get_by_test_id("reviews")).to_contain_text("Самочувствие: 4 · Настроение: 7")
    page.get_by_label("Настроение (1–10)").fill("8")
    page.get_by_test_id("save-review").click()
    expect(page.get_by_test_id("reviews")).to_contain_text("Настроение: 8")
    expect(page.get_by_test_id("reviews").get_by_role("listitem")).to_have_count(1)
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-day-review.png"), full_page=True)
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]

    other = fresh_page(browser, live_server)
    register(other, "bob@example.com")
    other.get_by_role("link", name="Итог дня").click()
    expect(other.get_by_text("Пока нет итогов дня.")).to_be_visible()
    other.context.close()


@pytest.mark.acceptance("kognis-d5q", "AC1")
@pytest.mark.e2e
def test_crisis_entry_shows_accessible_help_block(page: Page) -> None:
    """Запись с кризисной фразой сохраняется, интерфейс заметно показывает контакты помощи."""
    register(page, "ann@example.com")
    page.get_by_label("Что произошло и что вы чувствуете").fill("Не хочу больше жить")
    page.get_by_test_id("save-entry").click()
    block = page.get_by_test_id("help-block")
    expect(block).to_be_visible()
    expect(block.get_by_role("link", name="112")).to_be_visible()
    expect(page.get_by_test_id("entries")).to_contain_text("Не хочу больше жить")
    expect(page.get_by_test_id("disclaimer")).to_contain_text("не медицинская помощь")
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-crisis-help.png"), full_page=True)
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]


@pytest.mark.acceptance("kognis-50k", "AC3")
@pytest.mark.e2e
def test_progress_widget_and_achievements_page(page: Page) -> None:
    """Запись даёт опыт в виджете и достижение «Первая запись» с датой; axe без серьёзных."""
    register(page, "ann@example.com")
    expect(page.get_by_test_id("level")).to_have_text("Уровень 1")
    page.get_by_label("Что произошло и что вы чувствуете").fill("Первый шаг")
    page.get_by_test_id("save-entry").click()
    expect(page.get_by_test_id("xp")).to_have_text("Опыт: 10 из 50")
    expect(page.get_by_test_id("streak")).to_have_text("Серия: 1 дн.")
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-progress.png"), full_page=True)

    page.get_by_role("link", name="Достижения").click()
    item = page.get_by_test_id("achievements").get_by_role("listitem")
    expect(item).to_have_count(1)
    expect(item).to_contain_text("Первая запись")
    expect(item).to_contain_text("Получено: 20")
    page.screenshot(path=str(SCREENS / "e2e-achievements.png"), full_page=True)
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]


class CannedProvider:
    """Всегда отвечает корректным разбором; запись №1 — опора паттерна."""

    def complete(self, system: str, messages: Sequence[Message], schema: object = None) -> str:
        return json.dumps(
            {
                "summary": "Неделя прошла напряжённо, но вы держались.",
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
    """Приложение на свободном порту в фоне (свой провайдер ИИ вместо фейкового)."""
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


def check_axe(page: Page) -> None:
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]


@pytest.mark.acceptance("kognis-kai", "AC6")
@pytest.mark.e2e
def test_analysis_screen(browser: Browser, engine: Engine) -> None:
    """Экран разбора: согласие, результат с паттернами, вопросы; кризис без паттернов; axe."""
    with serve(create_app(engine, ai_provider=CannedProvider())) as url:
        page = fresh_page(browser, url)
        register(page, "ann@example.com")
        page.get_by_label("Что произошло и что вы чувствуете").fill("Сегодня страшно звонить")
        page.get_by_test_id("save-entry").click()
        expect(page.get_by_test_id("entries")).to_contain_text("страшно звонить")
        page.get_by_role("link", name="Разбор").click()
        run = page.get_by_test_id("run-analysis")
        expect(run).to_be_disabled()
        page.get_by_label("Согласен(на) передать записи").check()
        run.click()
        result = page.get_by_test_id("analysis-result")
        expect(result).to_contain_text("Избегание")
        expect(result).to_contain_text("страшно звонить")
        expect(page.get_by_test_id("mood")).to_be_visible()
        page.get_by_label("Что помогло бы начать?").fill("Позвонить утром")
        SCREENS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENS / "e2e-analysis.png"), full_page=True)
        check_axe(page)

        page.get_by_role("link", name="Дневник").click()
        page.get_by_label("Что произошло и что вы чувствуете").fill("Не хочу больше жить")
        page.get_by_test_id("save-entry").click()
        expect(page.get_by_test_id("help-block")).to_be_visible()
        page.get_by_role("link", name="Разбор").click()
        page.get_by_label("Согласен(на) передать записи").check()
        page.get_by_test_id("run-analysis").click()
        crisis = page.get_by_test_id("analysis-crisis")
        expect(crisis.get_by_role("link", name="112")).to_be_visible()
        expect(page.get_by_test_id("analysis-result")).to_have_count(0)
        page.screenshot(path=str(SCREENS / "e2e-analysis-crisis.png"), full_page=True)
        check_axe(page)
        page.context.close()


@pytest.mark.e2e
def test_no_serious_accessibility_violations(page: Page) -> None:
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]
