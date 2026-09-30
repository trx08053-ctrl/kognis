"""Логотип в шапке ведёт на главную страницу сайта: приёмочные e2e kognis-aoa (AC1, AC2)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
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


@pytest.fixture
def page(browser: Browser, live_server: str) -> Iterator[Page]:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    context = browser.new_context(locale="ru-RU")
    page = context.new_page()
    page.goto(live_server)
    yield page
    context.close()


@pytest.mark.acceptance("kognis-aoa", "AC1")
@pytest.mark.e2e
def test_signed_in_logo_opens_landing_and_button_returns_to_diary(page: Page) -> None:
    """Вошедший: клик по логотипу → лендинг без форм входа; «Открыть дневник» → дневник."""
    page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
    page.get_by_label("Email").fill("logo@example.com")
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    expect(page.get_by_test_id("whoami")).to_have_text("logo@example.com")

    page.get_by_role("link", name="Kognis — на главную страницу сайта").click()
    expect(page.get_by_role("heading", level=1)).to_contain_text("первый шаг к спокойствию")
    assert page.url.endswith("/welcome")
    expect(page.get_by_test_id("auth-submit")).to_have_count(0)

    page.get_by_test_id("open-diary-hero").click()
    expect(page.get_by_test_id("whoami")).to_have_text("logo@example.com")
    assert not page.url.endswith("/welcome")


@pytest.mark.acceptance("kognis-aoa", "AC2")
@pytest.mark.e2e
def test_guest_root_is_still_landing_with_auth_form(page: Page, live_server: str) -> None:
    """Гость: / — лендинг с формой входа, /welcome ведёт на /."""
    expect(page.get_by_role("heading", level=1)).to_contain_text("первый шаг к спокойствию")
    expect(page.get_by_role("heading", name="Вход")).to_be_visible()
    page.goto(f"{live_server}/welcome")
    expect(page.get_by_role("heading", name="Вход")).to_be_visible()
    assert page.url.rstrip("/") == live_server
