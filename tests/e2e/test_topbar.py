"""Компактная шапка и меню аватара (kognis-2zb): опыт — в «Профиле», email/тема/выход — в меню.

Скриншоты — в .evidence/screens/ (агент может открыть их и посмотреть на интерфейс).
"""

import importlib
import re
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


@pytest.fixture
def page(browser: Browser, live_server: str) -> Iterator[Page]:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    context = browser.new_context(viewport={"width": 1024, "height": 700}, locale="ru-RU")
    page = context.new_page()
    page.goto(live_server)
    yield page
    context.close()


def register(page: Page, email: str) -> None:
    page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
    page.get_by_label("Email").fill(email)
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    expect(page.get_by_test_id("user-menu")).to_be_visible()


@pytest.mark.acceptance("kognis-2zb", "AC1")
@pytest.mark.e2e
def test_topbar_is_compact_and_experience_lives_in_profile(page: Page) -> None:
    """Вместо двух постоянных блоков — одна строка: логотип, уровень/серия, аватар;
    полоски опыта нет на дневнике — она в разделе «Профиль»."""
    register(page, "topbar@example.com")
    expect(page.get_by_test_id("logo")).to_be_visible()
    expect(page.get_by_test_id("level")).to_have_text("Уровень 1")
    expect(page.get_by_test_id("days-30-badge")).to_be_visible()
    expect(page.get_by_test_id("user-menu")).to_be_visible()
    # второй постоянный блок (опыт) и реквизиты меню шапку больше не занимают
    expect(page.get_by_test_id("xp")).to_have_count(0)
    expect(page.get_by_test_id("progress")).to_have_count(0)
    expect(page.get_by_test_id("whoami")).to_have_count(0)
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-topbar.png"), full_page=True)

    page.get_by_role("link", name="Профиль").click()
    expect(page.get_by_test_id("progress")).to_be_visible()
    expect(page.get_by_test_id("xp")).to_have_text(re.compile(r"^Опыт: \d+ из \d+$"))


@pytest.mark.acceptance("kognis-2zb", "AC2")
@pytest.mark.e2e
def test_user_menu_holds_email_theme_and_logout(page: Page, live_server: str) -> None:
    """Меню аватара: email, смена темы, «Выйти»; Escape и клик вне закрывают меню."""
    register(page, "menu@example.com")
    avatar = page.get_by_test_id("user-menu")
    expect(avatar).to_have_attribute("aria-expanded", "false")
    avatar.click()
    expect(avatar).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_test_id("whoami")).to_have_text("menu@example.com")
    theme = page.get_by_test_id("theme-toggle")
    expect(theme).to_be_visible()
    expect(page.get_by_role("button", name="Выйти")).to_be_visible()
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-user-menu.png"))

    # Escape закрывает меню
    page.keyboard.press("Escape")
    expect(avatar).to_have_attribute("aria-expanded", "false")

    # клик вне меню тоже закрывает
    avatar.click()
    page.mouse.click(500, 400)
    expect(avatar).to_have_attribute("aria-expanded", "false")

    # тема переключается из меню
    avatar.click()
    before = theme.text_content()
    theme.click()
    expect(theme).not_to_have_text(before or "")

    # «Выйти» завершает сессию; до перезагрузки интерфейс прежний — известный баг kognis-zxb
    with page.expect_response("**/api/auth/logout") as response:
        page.get_by_role("button", name="Выйти").click()
    assert response.value.ok, response.value.status
    assert page.context.request.get(f"{live_server}/api/me").status == 401


@pytest.mark.acceptance("kognis-2zb", "AC3")
@pytest.mark.e2e
def test_profile_shows_experience_meter(page: Page) -> None:
    """В «Профиле» — полоска опыта и «Опыт: X из Y» из /api/progress."""
    register(page, "xp@example.com")
    page.get_by_label("Что произошло и что вы чувствуете").fill("Первый шаг")
    page.get_by_test_id("save-entry").click()
    page.get_by_role("link", name="Профиль").click()
    expect(page.get_by_test_id("xp")).to_have_text(re.compile(r"^Опыт: \d+ из \d+$"))
    expect(page.get_by_test_id("progress").get_by_role("progressbar")).to_be_visible()


@pytest.mark.acceptance("kognis-2zb", "AC4")
@pytest.mark.e2e
def test_topbar_and_menu_have_no_serious_a11y_violations(page: Page) -> None:
    """axe на новой шапке и в открытом меню: без нарушений serious/critical."""
    register(page, "axe-topbar@example.com")
    page.get_by_test_id("user-menu").click()
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-topbar-menu-open.png"))
