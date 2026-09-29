"""Лендинг для гостя в браузере: приёмочные e2e kognis-6sk (AC1–AC3).

Скриншоты — в .evidence/screens/ (обе темы, телефон).
"""

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from playwright.sync_api import Browser, Page, ViewportSize, expect, sync_playwright

Axe: Any = importlib.import_module("axe_playwright_python.sync_playwright").Axe

ROOT = Path(__file__).resolve().parents[2]
SCREENS = ROOT / ".evidence" / "screens"
VALID_PW = "correct horse"
DESKTOP: ViewportSize = {"width": 1280, "height": 800}
PHONE: ViewportSize = {"width": 390, "height": 844}
SECTIONS = [
    "Всё, чтобы лучше понимать себя",
    "Три шага от переживания к ясности",
    "Изменения, которые видно на графике",
    "Небольшие шаги — заметные перемены",
    "Читайте о психологии просто",
    "Частые вопросы",
    "Начните с одной записи сегодня",
]


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as err:
            pytest.fail(f"нет браузера для e2e — выполните `just setup-browsers` ({err})")
        yield b
        b.close()


def open_landing(
    browser: Browser,
    url: str,
    scheme: Literal["light", "dark"] = "light",
    viewport: ViewportSize = DESKTOP,
) -> Page:
    frontend = ROOT / "frontend"
    if (frontend / "package.json").exists() and not (frontend / "dist" / "index.html").exists():
        pytest.fail("фронтенд не собран — pnpm --dir frontend build (verify собирает сам)")
    context = browser.new_context(viewport=viewport, locale="ru-RU", color_scheme=scheme)
    page = context.new_page()
    page.goto(url)
    expect(page.get_by_role("heading", level=1)).to_contain_text("первый шаг к спокойствию")
    return page


def scroll_through(page: Page) -> None:
    """Прокрутка до конца: блоки появляются при попадании в экран."""
    height = cast("int", page.evaluate("document.body.scrollHeight"))
    for y in range(0, height + 800, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(60)
        if y > height:
            break
    page.wait_for_timeout(900)  # анимация появления и счётчики
    page.evaluate("window.scrollTo(0, 0)")  # липкая шапка — наверху снимка
    page.wait_for_timeout(100)


def check_axe(page: Page) -> None:
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [
        f"{v['id']}: {v['help']} {[n['target'] for n in v.get('nodes', [])][:5]}" for v in serious
    ]


@pytest.mark.acceptance("kognis-6sk", "AC1")
@pytest.mark.e2e
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_landing_sections_and_a11y(
    browser: Browser, live_server: str, scheme: Literal["light", "dark"]
) -> None:
    """Гость на / видит все разделы лендинга, фото загружены, нарушений axe нет в обеих темах."""
    page = open_landing(browser, live_server, scheme)
    problems: list[str] = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    for name in SECTIONS:
        expect(page.get_by_role("heading", level=2, name=name)).to_be_visible()
    expect(page.get_by_role("heading", name="Вход")).to_be_visible()
    expect(page.get_by_test_id("landing-disclaimer")).to_contain_text("112")
    scroll_through(page)
    broken = page.evaluate(
        "[...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src)"
    )
    assert broken == [], broken
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / f"e2e-landing-{scheme}.png"), full_page=True)
    check_axe(page)
    assert problems == []
    page.context.close()


@pytest.mark.acceptance("kognis-6sk", "AC1")
@pytest.mark.e2e
def test_landing_fits_phone(browser: Browser, live_server: str) -> None:
    """На телефоне нет горизонтальной прокрутки, форма входа доступна."""
    page = open_landing(browser, live_server, viewport=PHONE)
    scroll_through(page)
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, overflow
    expect(page.get_by_test_id("auth-submit")).to_be_visible()
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-landing-phone.png"), full_page=True)
    check_axe(page)
    page.context.close()


@pytest.mark.acceptance("kognis-6sk", "AC2")
@pytest.mark.e2e
def test_landing_cta_registers(browser: Browser, live_server: str) -> None:
    """«Начать вести дневник» → форма регистрации с фокусом в Email → после регистрации дневник."""
    page = open_landing(browser, live_server)
    page.get_by_test_id("cta-hero").click()
    expect(page.get_by_role("heading", name="Регистрация")).to_be_visible()
    expect(page.get_by_label("Email")).to_be_focused()
    page.get_by_label("Email").fill("ann@example.com")
    page.get_by_label("Пароль").fill(VALID_PW)
    page.get_by_test_id("auth-submit").click()
    expect(page.get_by_test_id("whoami")).to_have_text("ann@example.com")
    expect(page.get_by_label("Что произошло и что вы чувствуете")).to_be_visible()
    expect(page.get_by_role("heading", level=1)).to_have_text("Kognis")
    page.context.close()


@pytest.mark.acceptance("kognis-6sk", "AC3")
@pytest.mark.e2e
def test_landing_interactive(browser: Browser, live_server: str) -> None:
    """Демо разбора (мышь и стрелки), показатель графика, история, статья и FAQ."""
    page = open_landing(browser, live_server)
    lens = page.get_by_test_id("demo-lens")
    expect(lens).to_contain_text("Чтение мыслей")
    page.get_by_role("tab", name="ACT").click()
    expect(lens).to_contain_text("Слияние с мыслью")
    page.keyboard.press("ArrowRight")
    expect(page.get_by_role("tab", name="Схема-терапия")).to_be_focused()
    expect(lens).to_contain_text("схему «покорность»")

    page.get_by_role("button", name="Самочувствие", exact=True).click()
    expect(page.get_by_test_id("metric-delta")).to_have_text("+1,8 балла")

    page.get_by_role("button", name="Следующая история").click()
    expect(page.get_by_test_id("story")).to_contain_text("Марина")

    page.get_by_role("button", name="Читать статью").first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Пеннебейкер")
    expect(page.get_by_role("button", name="Закрыть статью")).to_be_focused()
    check_axe(page)
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()

    faq = page.locator("details").filter(has_text="Кто может прочитать мои записи?")
    faq.locator("summary").click()
    expect(faq).to_contain_text("Только вы")
    page.context.close()
