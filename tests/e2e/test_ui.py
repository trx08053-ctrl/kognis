"""Сквозной сценарий в браузере (Playwright): регистрация, запись, новый сеанс, изоляция, a11y.

Скриншоты — в .evidence/screens/ (агент может открыть их и посмотреть на интерфейс).
"""

import base64
import datetime as dt
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
from playwright.sync_api import Browser, Page, ViewportSize, expect, sync_playwright
from sqlalchemy import text as sql_text
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
    context = browser.new_context(viewport={"width": 1024, "height": 700}, locale="ru-RU")
    page = context.new_page()
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
    page.get_by_label("Теги", exact=True).fill("Работа, сон")
    page.get_by_role("button", name="тревога", exact=True).click()
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
    """Итог дня в браузере: шкалы-ползунки не выходят за 1–10 (kognis-0wr; проверка диапазона на
    сервере — tests/web/test_day_reviews.py); итог в истории; повторное сохранение за ту же дату
    не плодит записи; другой пользователь истории не видит."""
    register(page, "ann@example.com")
    page.get_by_role("link", name="Итог дня").click()
    slider = page.get_by_label("Самочувствие (1–10)")
    assert slider.evaluate("e => { e.value = '11'; return e.value }") == "10"

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


@pytest.fixture
def data_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ключ данных для записей «под замком»; объявляется до live_server, который читает env."""
    monkeypatch.setenv("KOGNIS_DATA_KEY", base64.b64encode(b"K" * 32).decode())


@pytest.mark.acceptance("kognis-83s", "AC4")
@pytest.mark.e2e
@pytest.mark.usefixtures("data_key")
def test_locked_entry_flow_and_accessibility(page: Page) -> None:
    """Запись под замком: заглушка без текста, неверный пароль — ошибка, верный — текст; axe."""
    register(page, "ann@example.com")
    page.get_by_label("Что произошло и что вы чувствуете").fill("Личное под замком")
    page.get_by_role("radio", name="Под замком").check()
    page.get_by_label("Пароль замка (от 8 символов). Забытый пароль восстановить нельзя.").fill(
        "замок-12345"
    )
    page.get_by_test_id("save-entry").click()
    entries = page.get_by_test_id("entries")
    expect(page.get_by_test_id("locked-stub")).to_be_visible()
    expect(entries).not_to_contain_text("Личное под замком")
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-locked.png"), full_page=True)
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]

    page.get_by_label("Пароль замка", exact=True).fill("неверный-пароль")
    page.get_by_role("button", name="Открыть").click()
    expect(entries.get_by_role("alert")).to_contain_text("неверный пароль замка")
    expect(entries).not_to_contain_text("Личное под замком")
    page.get_by_label("Пароль замка", exact=True).fill("замок-12345")
    page.get_by_role("button", name="Открыть").click()
    expect(page.get_by_test_id("opened-text")).to_have_text("Личное под замком")


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

    page.get_by_role("link", name="Профиль").click()
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
                "quest_ideas": ["Позвонить одному человеку"],
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
    assert not serious, [
        f"{v['id']}: {v['help']} {[n['target'] for n in v.get('nodes', [])][:5]}" for v in serious
    ]


@pytest.mark.acceptance("kognis-8f1", "AC1")
@pytest.mark.acceptance("kognis-8f1", "AC2")
@pytest.mark.e2e
def test_private_entry_encrypted_in_browser(page: Page, engine: Engine) -> None:
    """Приватная запись: в запросе и в БД нет открытого текста, в браузере открывается паролем,
    неверный пароль — понятная ошибка; предупреждение о невосстановимости; axe."""
    text, password = "Очень личная мысль", "пароль-записи-1"
    sent: list[str] = []
    page.on(
        "request",
        lambda r: sent.append(r.post_data or "") if r.url.endswith("/api/entries") else None,
    )
    register(page, "ann@example.com")
    page.get_by_label("Что произошло и что вы чувствуете").fill(text)
    page.get_by_role("radio", name="Приватная").check()
    expect(page.get_by_test_id("private-warning")).to_contain_text("восстановить его нельзя")
    page.get_by_label("Пароль записи (от 8 символов)").fill(password)
    page.get_by_label("Повторите пароль").fill(password)
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-private-form.png"), full_page=True)
    check_axe(page)
    page.get_by_test_id("save-entry").click()
    expect(page.get_by_test_id("private-stub")).to_be_visible()
    expect(page.get_by_test_id("entries")).not_to_contain_text(text)

    posts = [body for body in sent if body]
    assert posts, "запрос на создание не перехвачен"
    assert all(text not in body and password not in body for body in posts)
    with engine.connect() as conn:
        dump = repr(conn.execute(sql_text("SELECT * FROM entries")).all())
    assert text not in dump
    assert password not in dump
    assert "PBKDF2-SHA256" in dump

    page.reload()
    page.get_by_label("Пароль записи", exact=True).fill("неверный-пароль")
    page.get_by_role("button", name="Расшифровать").click()
    expect(page.get_by_role("alert")).to_contain_text("Неверный пароль")
    page.get_by_label("Пароль записи", exact=True).fill(password)
    page.get_by_role("button", name="Расшифровать").click()
    expect(page.get_by_test_id("private-text")).to_have_text(text)
    page.screenshot(path=str(SCREENS / "e2e-private-opened.png"), full_page=True)
    check_axe(page)


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


@pytest.mark.acceptance("kognis-1yv", "AC2")
@pytest.mark.e2e
def test_analysis_uses_user_timezone_not_browser_or_server(
    browser: Browser, engine: Engine
) -> None:
    """Пояс браузера (Auckland, UTC+12) не совпадает с поясом сервера (UTC): «сегодня» берётся
    из профиля, запись за «сегодня» попадает в период разбора."""
    utc_evening = dt.datetime(2026, 9, 1, 20, 0, tzinfo=dt.UTC)  # в Окленде уже 2 сентября
    app = create_app(engine, ai_provider=CannedProvider(), clock=lambda: utc_evening)
    with serve(app) as url:
        context = browser.new_context(
            viewport={"width": 1024, "height": 700}, locale="ru-RU", timezone_id="Pacific/Auckland"
        )
        page = context.new_page()
        page.goto(url)
        register(page, "ann@example.com")
        page.get_by_label("Что произошло и что вы чувствуете").fill("Сегодня страшно звонить")
        page.get_by_test_id("save-entry").click()
        expect(page.get_by_test_id("entries")).to_contain_text("2026-09-02")
        page.get_by_role("link", name="Разбор").click()
        expect(page.get_by_label("По дату")).to_have_value("2026-09-02")
        page.get_by_label("Согласен(на) передать записи").check()
        page.get_by_test_id("run-analysis").click()
        expect(page.get_by_test_id("analysis-result")).to_contain_text("Избегание")
        context.close()


@pytest.mark.acceptance("kognis-99x", "AC4")
@pytest.mark.e2e
def test_quests_screen(browser: Browser, engine: Engine) -> None:
    """Экран «Квесты»: квест из анализа и из библиотеки, отметка шагов, квиз; axe."""
    with serve(create_app(engine, ai_provider=CannedProvider())) as url:
        page = fresh_page(browser, url)
        register(page, "ann@example.com")
        page.get_by_label("Что произошло и что вы чувствуете").fill("Сегодня страшно звонить")
        page.get_by_test_id("save-entry").click()
        expect(page.get_by_test_id("xp")).to_have_text("Опыт: 10 из 50")
        page.get_by_role("link", name="Разбор").click()
        page.get_by_label("Согласен(на) передать записи").check()
        page.get_by_test_id("run-analysis").click()
        page.get_by_role("button", name="Принять квест: Позвонить одному человеку").click()
        expect(page.get_by_role("status")).to_contain_text("Квест принят")

        page.get_by_label("Разделы").get_by_role("link", name="Квесты").click()
        quest = page.get_by_test_id("quest")
        expect(quest).to_have_count(1)
        expect(quest).to_contain_text("Выполнено шагов: 0 из 3")
        quest.get_by_role("button", name="Отметить").first.click()
        expect(quest).to_contain_text("Выполнено шагов: 1 из 3")
        expect(page.get_by_test_id("xp")).to_have_text("Опыт: 25 из 50")

        page.get_by_role("button", name="Принять: Поймай автоматическую мысль").click()
        expect(page.get_by_test_id("quest")).to_have_count(2)
        expect(
            page.get_by_role("button", name="Принять: Поймай автоматическую мысль")
        ).to_be_disabled()

        quiz = page.get_by_test_id("quiz").first
        for box in quiz.get_by_role("textbox").all():
            box.fill("Ответ")
        quiz.get_by_role("button", name="Сохранить ответы").click()
        expect(quiz.get_by_test_id("quiz-done")).to_contain_text("+10")
        expect(page.get_by_test_id("xp")).to_have_text("Опыт: 35 из 50")
        SCREENS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENS / "e2e-quests.png"), full_page=True)
        check_axe(page)

        # после перезагрузки прогресс на месте, квиз сегодня уже пройден
        page.reload()
        expect(page.get_by_test_id("quest").first).to_be_visible()
        expect(page.get_by_test_id("quiz-done")).to_have_count(1)
        page.context.close()


@pytest.mark.e2e
def test_no_serious_accessibility_violations(page: Page) -> None:
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    violations = cast("list[dict[str, Any]]", Axe().run(page).response["violations"])
    serious = [v for v in violations if v["impact"] in {"serious", "critical"}]
    assert not serious, [f"{v['id']}: {v['help']}" for v in serious]


def add_entry(page: Page, text: str, tags: str = "", emotions: str = "") -> None:
    page.get_by_label("Что произошло и что вы чувствуете").fill(text)
    page.get_by_label("Теги", exact=True).fill(tags)
    page.get_by_label("Своя эмоция").fill(emotions)
    page.get_by_test_id("save-entry").click()
    expect(page.get_by_test_id("entries")).to_contain_text(text)


def is_dark(page: Page) -> bool:
    return bool(page.evaluate("document.documentElement.classList.contains('dark')"))


@pytest.mark.acceptance("kognis-0wr", "AC1")
@pytest.mark.e2e
def test_dark_theme_follows_system_and_is_remembered(browser: Browser, live_server: str) -> None:
    """По умолчанию тема как в системе; переключатель включает тёмную, выбор переживает reload."""
    light = browser.new_context(color_scheme="light", locale="ru-RU")
    lp = light.new_page()
    lp.goto(live_server)
    assert not is_dark(lp)
    dark = browser.new_context(color_scheme="dark", locale="ru-RU")
    dp = dark.new_page()
    dp.goto(live_server)
    assert is_dark(dp)
    dark.close()

    register(lp, "ann@example.com")
    toggle = lp.get_by_test_id("theme-toggle")
    toggle.click()
    assert is_dark(lp)
    lp.reload()  # выбор хранится в браузере
    expect(lp.get_by_test_id("whoami")).to_be_visible()
    assert is_dark(lp)
    lp.get_by_test_id("theme-toggle").click()
    lp.reload()
    expect(lp.get_by_test_id("whoami")).to_be_visible()
    assert not is_dark(lp)
    light.close()


@pytest.mark.acceptance("kognis-0wr", "AC2")
@pytest.mark.e2e
def test_advanced_mode_shows_charts_and_filters_and_is_kept_on_server(
    browser: Browser, live_server: str, page: Page
) -> None:
    """Простой режим скрывает графики и фильтры; Advanced их открывает и запоминается на сервере."""
    register(page, "ann@example.com")
    add_entry(page, "Про работу", tags="работа", emotions="тревога")
    add_entry(page, "Про сон", tags="сон", emotions="покой")
    expect(page.get_by_test_id("mood-chart")).to_have_count(0)
    expect(page.get_by_test_id("entry-filters")).to_have_count(0)

    page.get_by_role("link", name="Профиль").click()
    page.get_by_test_id("advanced-toggle").check()
    page.get_by_role("link", name="Дневник", exact=True).click()
    expect(page.get_by_test_id("mood-chart")).to_be_visible()
    filters = page.get_by_test_id("entry-filters")
    expect(filters).to_be_visible()
    filters.get_by_label("Тег").select_option("сон")
    expect(page.get_by_test_id("entries").get_by_role("listitem")).to_have_count(1)
    expect(page.get_by_test_id("entries")).to_contain_text("Про сон")
    filters.get_by_label("Тег").select_option("")
    filters.get_by_label("Эмоция").select_option("тревога")
    expect(page.get_by_test_id("entries")).to_contain_text("Про работу")
    expect(page.get_by_test_id("entries").get_by_role("listitem")).to_have_count(1)

    other = fresh_page(browser, live_server)  # другой браузер: режим пришёл с сервера
    login(other, "ann@example.com")
    expect(other.get_by_test_id("mood-chart")).to_be_visible()
    other.get_by_role("link", name="Профиль").click()
    expect(other.get_by_test_id("advanced-toggle")).to_be_checked()
    other.get_by_test_id("advanced-toggle").uncheck()
    other.get_by_role("link", name="Дневник", exact=True).click()
    expect(other.get_by_test_id("mood-chart")).to_have_count(0)
    other.context.close()
    page.get_by_role("link", name="Профиль").click()
    page.reload()
    expect(page.get_by_test_id("advanced-toggle")).not_to_be_checked()


@pytest.mark.acceptance("kognis-0wr", "AC3")
@pytest.mark.e2e
def test_key_screens_have_no_serious_a11y_violations_in_both_themes(
    browser: Browser, live_server: str
) -> None:
    """axe на главной (простой и Advanced), итоге дня и профиле — в светлой и тёмной теме."""
    SCREENS.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        viewport={"width": 1024, "height": 900}, locale="ru-RU", color_scheme="light"
    )
    page = context.new_page()
    page.goto(live_server)
    register(page, "ann@example.com")
    page.get_by_role("link", name="Итог дня").click()
    page.get_by_label("Настроение (1–10)").fill("7")
    page.get_by_test_id("save-review").click()
    expect(page.get_by_test_id("reviews")).to_contain_text("Настроение: 7")
    page.get_by_role("link", name="Дневник").click()
    add_entry(page, "Спокойный день", tags="дом", emotions="покой")
    page.get_by_test_id("onboarding").wait_for()

    for theme in ("light", "dark"):
        if theme == "dark":
            page.get_by_test_id("theme-toggle").click()
            assert is_dark(page)
        for name, action in [
            ("home", ""),
            ("home-advanced", "advanced"),
            ("day", "Итог дня"),
            ("profile", "Профиль"),
        ]:
            if action == "advanced":
                page.get_by_role("link", name="Профиль").click()
                page.get_by_test_id("advanced-toggle").check()
                page.get_by_role("link", name="Дневник", exact=True).click()
                expect(page.get_by_test_id("mood-chart")).to_be_visible()
            elif action:
                page.get_by_role("link", name=action).click()
                page.get_by_role("heading", level=2).first.wait_for()
            page.wait_for_timeout(200)  # отрисовка графика
            page.screenshot(path=str(SCREENS / f"0wr-{name}-{theme}.png"), full_page=True)
            check_axe(page)
        page.get_by_role("link", name="Профиль").click()
        page.get_by_test_id("advanced-toggle").uncheck()
        page.get_by_role("link", name="Дневник", exact=True).click()
    context.close()


@pytest.mark.acceptance("kognis-yaj", "AC2")
@pytest.mark.e2e
def test_interface_works_under_security_headers(browser: Browser, live_server: str) -> None:
    """Со строгим CSP интерфейс грузится и работает, нарушений CSP в консоли нет; axe; скриншот."""
    context = browser.new_context(viewport={"width": 1024, "height": 700}, locale="ru-RU")
    page = context.new_page()
    problems: list[str] = []
    page.on(
        "console", lambda m: problems.append(m.text) if m.type in {"error", "warning"} else None
    )
    page.on("pageerror", lambda e: problems.append(str(e)))
    response = page.goto(live_server)
    assert response is not None
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    register(page, "ann@example.com")
    add_entry(page, "Сегодня был спокойный день")
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "e2e-hardening.png"), full_page=True)
    check_axe(page)
    context.close()
    assert not [p for p in problems if "Content Security Policy" in p], problems


ROUTES = [
    ("home", "Дневник"),
    ("day", "Итог дня"),
    ("analysis", "Разбор"),
    ("quests", "Квесты"),
    ("profile", "Профиль"),
]
MOBILE = ViewportSize(width=375, height=812)
DESKTOP = ViewportSize(width=1280, height=800)


def no_horizontal_scroll(page: Page) -> bool:
    return bool(
        page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
    )


@pytest.mark.acceptance("kognis-tm0", "AC1")
@pytest.mark.acceptance("kognis-tm0", "AC3")
@pytest.mark.acceptance("kognis-tm0", "AC4")
@pytest.mark.acceptance("kognis-w58", "AC4")
@pytest.mark.e2e
def test_responsive_navigation_screens_and_a11y(browser: Browser, live_server: str) -> None:
    """375 px: нет горизонтальной прокрутки, навигация — нижняя панель; 1280 px — боковая.
    Скриншоты экранов в обеих темах и axe (обе темы, оба размера) — в .evidence/screens/tm0-*."""
    SCREENS.mkdir(parents=True, exist_ok=True)
    for size_name, size in (("mobile", MOBILE), ("desktop", DESKTOP)):
        context = browser.new_context(viewport=size, locale="ru-RU", color_scheme="light")
        page = context.new_page()
        page.goto(live_server)
        register(page, f"{size_name}@example.com")
        nav = page.get_by_role("navigation", name="Разделы")
        box = nav.bounding_box()
        assert box is not None
        if size_name == "mobile":
            assert box["y"] + box["height"] >= size["height"] - 1, "панель не внизу экрана"
            assert box["width"] >= size["width"] - 1, "панель не на всю ширину"
        else:
            assert box["x"] == 0
            assert box["width"] < 300, "боковая панель слишком широкая"
            assert box["height"] >= size["height"] - 1, "панель не на всю высоту"
        for theme in ("light", "dark"):
            if theme == "dark":
                page.get_by_test_id("theme-toggle").click()
                assert is_dark(page)
            for name, link in ROUTES:
                page.get_by_role("link", name=link, exact=True).click()
                page.get_by_role("heading", level=2).first.wait_for()
                assert no_horizontal_scroll(page), f"{name}/{size_name}/{theme}: прокрутка"
                expect(nav).to_be_visible()
                clipped = nav.get_by_role("link").evaluate_all(
                    "els => els.filter(e => e.scrollWidth > e.clientWidth).map(e => e.textContent)"
                )
                assert not clipped, f"подписи навигации обрезаны: {clipped}"
                shot = SCREENS / f"tm0-{name}-{size_name}-{theme}.png"
                page.screenshot(path=str(shot), full_page=True)
                check_axe(page)
            # форма записи с раскрытым режимом «Под замком»
            page.get_by_role("link", name="Дневник", exact=True).click()
            page.get_by_role("radio", name="Под замком").check()
            assert no_horizontal_scroll(page)
            page.screenshot(
                path=str(SCREENS / f"tm0-entry-{size_name}-{theme}.png"), full_page=True
            )
            check_axe(page)
            page.get_by_role("radio", name="Обычная").check()
        context.close()


@pytest.mark.acceptance("kognis-tm0", "AC2")
@pytest.mark.e2e
def test_entry_form_chips_and_segmented_protection(page: Page) -> None:
    """Эмоции — чипы (словарь + своя), теги — чипы, режим защиты — три переключателя;
    запись с выбранными чипами сохраняется; подсказка меняется вместе с режимом."""
    register(page, "ann@example.com")
    group = page.get_by_role("radiogroup", name="Режим защиты")
    expect(group.get_by_role("radio")).to_have_count(3)
    for label in ("Обычная", "Под замком", "Приватная"):
        expect(group.get_by_role("radio", name=label)).to_be_attached()
    expect(group.get_by_role("radio", name="Обычная")).to_be_checked()

    joy = page.get_by_role("button", name="радость", exact=True)
    expect(joy).to_have_attribute("aria-pressed", "false")
    joy.click()
    expect(joy).to_have_attribute("aria-pressed", "true")
    page.get_by_label("Своя эмоция").fill("предвкушение,")
    expect(page.get_by_role("button", name="предвкушение", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    page.get_by_label("Теги", exact=True).fill("дом, семья,")
    expect(page.get_by_role("button", name="Убрать тег: дом")).to_be_visible()
    page.get_by_role("button", name="Убрать тег: семья").click()

    page.get_by_role("radio", name="Под замком").check()
    expect(page.get_by_text("Текст закрыт паролем")).to_be_visible()
    page.get_by_role("radio", name="Обычная").check()
    expect(page.get_by_text("Текст хранится на сервере")).to_be_visible()

    page.get_by_label("Что произошло и что вы чувствуете").fill("Хороший вечер")
    page.get_by_test_id("save-entry").click()
    entries = page.get_by_test_id("entries")
    expect(entries).to_contain_text("Хороший вечер")
    expect(entries).to_contain_text("радость")
    expect(entries).to_contain_text("предвкушение")
    expect(entries).to_contain_text("#дом")
    expect(entries).not_to_contain_text("#семья")


@pytest.mark.acceptance("kognis-w58", "AC1")
@pytest.mark.acceptance("kognis-ndp", "AC1")
@pytest.mark.e2e
def test_sidebar_stays_visible_and_full_height_on_long_page(
    browser: Browser, live_server: str
) -> None:
    """Длинная страница на десктопе: после прокрутки меню на месте, на всю высоту окна, с фоном."""
    context = browser.new_context(viewport=DESKTOP, locale="ru-RU", color_scheme="light")
    page = context.new_page()
    page.goto(live_server)
    register(page, "ann@example.com")
    page.evaluate("document.querySelector('main').style.minHeight = '4000px'")
    page.mouse.wheel(0, 2500)
    deadline = time.monotonic() + 5
    while page.evaluate("window.scrollY") <= 1000:
        assert time.monotonic() < deadline, "страница не прокрутилась"
        page.wait_for_timeout(50)
    nav = page.get_by_role("navigation", name="Разделы")
    expect(nav).to_be_visible()
    box = nav.bounding_box()
    assert box is not None
    assert box["y"] == 0
    assert box["height"] >= DESKTOP["height"] - 1
    background = nav.evaluate("e => getComputedStyle(e).backgroundColor")
    assert background not in {"rgba(0, 0, 0, 0)", "transparent"}
    # фон колонки меню продолжается на всю высоту страницы (важно и для полноэкранных снимков)
    layout = page.locator(".layout")
    assert layout.evaluate("e => getComputedStyle(e).backgroundImage").startswith("linear-gradient")
    assert layout.evaluate("e => e.getBoundingClientRect().height") >= 4000
    context.close()


@pytest.mark.acceptance("kognis-w58", "AC2")
@pytest.mark.e2e
def test_settings_live_on_profile_page_and_are_saved(browser: Browser, live_server: str) -> None:
    """Advanced и часовой пояс — на «Профиле» и сохраняются на сервере; на «Дневнике» их нет."""
    page = fresh_page(browser, live_server)
    register(page, "ann@example.com")
    expect(page.get_by_test_id("advanced-toggle")).to_have_count(0)
    expect(page.get_by_test_id("timezone-select")).to_have_count(0)

    page.get_by_role("link", name="Профиль").click()
    expect(page.get_by_role("heading", name="Профиль", level=2)).to_be_visible()
    page.get_by_test_id("advanced-toggle").check()
    page.get_by_test_id("timezone-select").select_option("Asia/Vladivostok")
    expect(page.get_by_test_id("timezone-select")).to_have_value("Asia/Vladivostok")

    page.reload()
    expect(page.get_by_test_id("advanced-toggle")).to_be_checked()
    expect(page.get_by_test_id("timezone-select")).to_have_value("Asia/Vladivostok")
    page.get_by_role("link", name="Дневник", exact=True).click()
    expect(page.get_by_test_id("advanced-toggle")).to_have_count(0)
    expect(page.get_by_test_id("timezone-select")).to_have_count(0)
    page.context.close()


@pytest.mark.acceptance("kognis-w58", "AC3")
@pytest.mark.e2e
def test_theme_button_name_describes_action(browser: Browser, live_server: str) -> None:
    """В светлой теме кнопка «Тёмная тема», в тёмной — «Светлая тема»; клик переключает тему."""
    context = browser.new_context(viewport=DESKTOP, locale="ru-RU", color_scheme="light")
    page = context.new_page()
    page.goto(live_server)
    register(page, "ann@example.com")
    assert not is_dark(page)
    page.get_by_role("button", name="Тёмная тема").click()
    assert is_dark(page)
    expect(page.get_by_role("button", name="Тёмная тема")).to_have_count(0)
    page.get_by_role("button", name="Светлая тема").click()
    assert not is_dark(page)
    expect(page.get_by_role("button", name="Тёмная тема")).to_be_visible()
    context.close()
