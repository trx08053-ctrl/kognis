"""Достижения по уровням и категориям и баланс XP по HTTP (kognis-0a8, AC1–AC2)."""

import datetime as dt
import json
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.analysis import DIRECTIONS
from kognis.db import transaction
from kognis.gameplay._achievements import DIRECTIONS_TOTAL, QUIZZES_TOTAL
from kognis.gameplay._infra import ProgressRepository, achievements_table
from kognis.gameplay._quests import QUIZZES
from kognis.web import create_app

from .test_gameplay import CLOCKS, Clock, at, progress, signup

START = dt.date(2026, 9, 1)


class Analyst:
    """Провайдер с готовым разбором и уточняющим вопросом."""

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        return json.dumps(
            {
                "summary": "Неделя.",
                "patterns": [],
                "questions": ["Что помогло?"],
                "quest_ideas": [],
            }
        )


@pytest.fixture
def clock() -> Clock:
    current = Clock(START)
    CLOCKS[:] = [current]
    return current


@pytest.fixture
def api(engine: Engine, clock: Clock) -> TestClient:
    client = TestClient(create_app(engine, clock=clock, ai_provider=Analyst()))
    signup(client)
    return client


def day_n(n: int) -> str:
    return (START + dt.timedelta(days=n)).isoformat()


def note(
    client: TestClient, day: str, marks: list[str] | None = None, text: str = "Заметка"
) -> None:
    at(day)
    response = client.post("/api/entries", json={"text": text, "date": day, "marks": marks or []})
    assert response.status_code == 201, response.text


def codes(client: TestClient) -> set[str]:
    return {a["code"] for a in progress(client)["achievements"]}


def category(client: TestClient, name: str) -> dict[str, Any]:
    return next(c for c in progress(client)["categories"] if c["category"] == name)


def test_targets_match_the_source_of_truth() -> None:
    assert len(DIRECTIONS) == DIRECTIONS_TOTAL
    assert len(QUIZZES) == QUIZZES_TOTAL


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_consistency_levels_follow_days_with_diary(api: TestClient) -> None:
    for n in range(6):
        note(api, day_n(n))
    assert "consistency_1" not in codes(api)
    assert category(api, "consistency")["next_target"] == 7
    note(api, day_n(6))
    assert "consistency_1" in codes(api)
    # пропуски не мешают: считаются дни с дневником, а не подряд
    for n in range(8, 31):
        note(api, day_n(n))
    assert {"consistency_1", "consistency_2"} <= codes(api)
    assert "consistency_3" not in codes(api)
    mid = category(api, "consistency")
    assert (mid["value"], mid["next_target"]) == (30, 100)
    for n in range(31, 101):
        note(api, day_n(n))
    gold = category(api, "consistency")
    assert gold["next_target"] is None
    assert all(level["earned_on"] for level in gold["levels"])


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_depth_counts_reflections_with_step_or_insight_only(api: TestClient) -> None:
    for n in range(5):  # «хорошее» и «переформулировка» в «Глубину» не входят
        note(api, day_n(n), ["good", "reframe"])
    assert category(api, "depth")["value"] == 0
    for n in range(5, 10):
        note(api, day_n(n), ["step" if n % 2 else "insight"])
    assert category(api, "depth")["value"] == 5
    assert "depth_1" in codes(api)
    assert "depth_2" not in codes(api)


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_care_counts_completed_quest_steps(api: TestClient) -> None:
    for _ in range(2):  # второй раз квест принимается после завершения первого
        quest = api.post("/api/quests", json={"template": "catch_thought"}).json()
        for idx in range(len(quest["steps"])):
            assert api.post(f"/api/quests/{quest['id']}/steps/{idx}/done", json={}).is_success
        if _ == 0:
            assert "care_1" not in codes(api)  # 4 шага из 5
    assert category(api, "care")["value"] == 8
    assert "care_1" in codes(api)
    assert "care_2" not in codes(api)


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_explorer_counts_directions_and_quizzes_and_gold_needs_all(api: TestClient) -> None:
    note(api, day_n(0))
    period = {"consent": True, "start": day_n(0), "end": day_n(6)}
    for direction in DIRECTIONS[:2]:
        assert api.post("/api/analyses", json={**period, "direction": direction.code}).is_success
    assert "explorer_1" in codes(api)
    assert "explorer_2" not in codes(api)
    api.post("/api/analyses", json={**period, "direction": DIRECTIONS[0].code})  # повтор — 409
    assert category(api, "explorer")["value"] == 2
    for direction in DIRECTIONS[2:4]:
        assert api.post("/api/analyses", json={**period, "direction": direction.code}).is_success
    assert "explorer_2" in codes(api)
    assert "explorer_3" not in codes(api)
    last = api.post("/api/analyses", json={**period, "direction": DIRECTIONS[4].code}).json()
    assert "explorer_3" not in codes(api)  # направления пройдены, квизы — нет
    assert api.post(
        f"/api/analyses/{last['id']}/answers", json={"answers": ["Разговор"], "consent": True}
    ).is_success
    for quiz in api.get("/api/quizzes").json():
        body = {"answers": ["Ответ"] * len(quiz["questions"])}
        assert api.post(f"/api/quizzes/{quiz['code']}/answers", json=body).is_success
    assert "explorer_3" in codes(api)


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_hidden_warm_achievements_show_question_mark_until_earned(api: TestClient) -> None:
    before = progress(api)["hidden"]
    assert [h["earned_on"] for h in before] == [None, None, None]
    note(api, day_n(0))
    note(api, day_n(8), ["good"])  # вернулся после паузы + первая благодарность
    now = {h["code"]: h["earned_on"] for h in progress(api)["hidden"]}
    assert now["comeback"]
    assert now["first_gratitude"]
    assert now["year_diary"] is None
    note(api, day_n(366))
    assert {h["code"]: h["earned_on"] for h in progress(api)["hidden"]}["year_diary"]


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_short_break_is_not_a_comeback(api: TestClient) -> None:
    note(api, day_n(0))
    note(api, day_n(7))  # шесть пустых дней — ещё не пауза
    assert not {h["code"]: h["earned_on"] for h in progress(api)["hidden"]}["comeback"]


@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_achievements_are_never_granted_twice(api: TestClient, engine: Engine) -> None:
    for n in range(7):
        note(api, day_n(n))
    for _ in range(3):
        progress(api)
    with transaction(engine) as session:
        repo = ProgressRepository(session)
        repo.add_achievement(
            1, "consistency_1", START
        )  # повтор тихо игнорируется (уникальность в БД)
        repo.add_achievement(1, "consistency_1", START)
        total = session.execute(
            select(func.count())
            .select_from(achievements_table)
            .where(achievements_table.c.code == "consistency_1")
        ).scalar_one()
    assert total == 1


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_text_length_and_tone_do_not_change_xp(api: TestClient) -> None:
    note(api, day_n(0), text="Плохо.")
    short = progress(api)["xp"]
    note(api, day_n(1), text="Всё ужасно и грустно. " * 200)
    assert progress(api)["xp"] - short == short == 10
    assert all(not a["code"].startswith("depth") for a in progress(api)["achievements"])


@pytest.mark.acceptance("kognis-0a8", "AC1")
def test_unknown_mark_is_rejected(api: TestClient) -> None:
    response = api.post("/api/entries", json={"text": "x", "marks": ["sad"]})
    assert response.status_code == 422
    response = api.put(
        f"/api/day-reviews/{day_n(0)}", json={"wellbeing": 5, "mood": 5, "marks": ["sad"]}
    )
    assert response.status_code == 422
