"""Сквозной сценарий в браузере (Playwright): регистрация через форму, сохранение, доступность.

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
def page(browser: Browser, live_server: str) -> Iterator[Page]:
    frontend = ROOT / "frontend"
    if (frontend / "package.json").exists() and not (frontend / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    page = browser.new_page(viewport={"width": 1024, "height": 700})
    page.goto(live_server)
    yield page
    page.close()


@pytest.mark.e2e
def test_register_via_form_and_survive_reload(page: Page) -> None:
    page.get_by_label("Имя пользователя").fill("Ann")
    page.get_by_test_id("register").click()
    expect(page.get_by_test_id("users")).to_have_text("Ann")
    page.reload()
    expect(page.get_by_test_id("users")).to_contain_text("Ann")
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-register.png"), full_page=True)


@pytest.mark.e2e
def test_blank_name_shows_error(page: Page) -> None:
    page.get_by_label("Имя пользователя").fill("   ")
    page.get_by_test_id("register").click()
    expect(page.get_by_role("alert")).to_contain_text("пуст")


@pytest.mark.e2e
def test_no_serious_accessibility_violations(page: Page) -> None:
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]
