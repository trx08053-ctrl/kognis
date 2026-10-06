"""Постраничные списки в браузере: приёмочный e2e kognis-3mh (AC3)."""

import datetime as dt
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

VALID_PW = "correct horse"
TOTAL = 45


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
    context = browser.new_context(viewport={"width": 1024, "height": 700}, locale="ru-RU")
    page = context.new_page()
    page.goto(live_server)
    yield page
    context.close()


@pytest.mark.acceptance("kognis-3mh", "AC3")
@pytest.mark.e2e
def test_first_page_shown_and_more_loads_next(page: Page, live_server: str) -> None:
    page.get_by_role("button", name="Нет аккаунта? Зарегистрироваться").click()
    page.get_by_label("Email").fill("ann@example.com")
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    page.get_by_test_id("user-menu").click()
    expect(page.get_by_test_id("whoami")).to_have_text("ann@example.com")
    page.keyboard.press("Escape")

    # год записей и итогов «задним числом» — через API того же сеанса
    api = page.context.request
    start = dt.date(2026, 1, 1)
    for n in range(TOTAL):
        day = start + dt.timedelta(days=n)
        body = {"text": f"запись {n}", "date": str(day), "tags": ["работа" if n % 2 else "дом"]}
        assert api.post(f"{live_server}/api/entries", data=body).status == 201
        review = {"wellbeing": 5, "mood": 5, "reflection": f"итог {n}"}
        assert api.put(f"{live_server}/api/day-reviews/{day}", data=review).status == 200

    page.get_by_role("link", name="Профиль").click()
    page.get_by_test_id("advanced-toggle").check()
    page.get_by_role("link", name="Дневник", exact=True).click()

    items = page.get_by_test_id("entries").locator("li")
    expect(items).to_have_count(30)  # первая страница
    expect(page.get_by_test_id("entries")).to_contain_text(f"запись {TOTAL - 1}")
    expect(page.get_by_test_id("entries")).not_to_contain_text("запись 0")
    page.get_by_test_id("more-entries").click()
    expect(items).to_have_count(TOTAL)
    expect(page.get_by_test_id("entries")).to_contain_text("запись 0")
    expect(page.get_by_test_id("more-entries")).to_have_count(0)

    # фильтр по тегу работает на сервере и начинает список с первой страницы
    page.get_by_test_id("entry-filters").get_by_label("Тег").select_option("работа")
    expect(items).to_have_count(TOTAL // 2)
    expect(page.get_by_test_id("entries")).not_to_contain_text("#дом")

    # итоги дня — тоже страницами
    page.get_by_role("link", name="Итог дня").click()
    reviews = page.get_by_test_id("reviews").locator("li")
    expect(reviews).to_have_count(30)
    page.get_by_test_id("more-reviews").click()
    expect(reviews).to_have_count(TOTAL)
