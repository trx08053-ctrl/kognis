"""Сквозной сценарий в браузере (Playwright): регистрация, запись, новый сеанс, изоляция, a11y.

Скриншоты — в .evidence/screens/ (агент может открыть их и посмотреть на интерфейс).
"""

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

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
def test_no_serious_accessibility_violations(page: Page) -> None:
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]
