"""Квесты, челленджи и квизы-рефлексии по HTTP: приёмочные тесты kognis-99x (AC1–AC3)."""

import datetime as dt
import json
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

PW = "correct horse"
LIBRARY_QUEST = "catch_thought"  # 4 шага
CHALLENGE = "activation_5"  # 5 шагов, по одному в день
ANSWERS = ["Разговор с друзьями", "Получилось начать", "Начал бы раньше"]


class Clock:
    def __init__(self, day: dt.date) -> None:
        self.day = day

    def __call__(self) -> dt.date:
        return self.day


class OneAnalysis:
    """Провайдер, отвечающий одним готовым анализом с идеями для квестов."""

    def __init__(self, ideas: list[str]) -> None:
        self.ideas = ideas

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        return json.dumps(
            {
                "summary": "Неделя прошла с тревогой.",
                "patterns": [],
                "questions": [],
                "quest_ideas": self.ideas,
            }
        )


@pytest.fixture
def clock() -> Clock:
    return Clock(dt.date(2026, 9, 1))


def make(engine: Engine, clock: Clock, email: str = "ann@example.com") -> TestClient:
    client = TestClient(
        create_app(engine, today=clock, ai_provider=OneAnalysis(["Позвонить другу"]))
    )
    r = client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return client


def xp(client: TestClient) -> int:
    return int(client.get("/api/progress").json()["xp"])


def accept(client: TestClient, code: str = LIBRARY_QUEST) -> dict[str, Any]:
    r = client.post("/api/quests", json={"template": code})
    assert r.status_code == 201
    body: dict[str, Any] = r.json()
    return body


def done(client: TestClient, quest_id: int, idx: int) -> Any:
    return client.post(f"/api/quests/{quest_id}/steps/{idx}/done", json={})


@pytest.mark.acceptance("kognis-99x", "AC1")
def test_accept_from_library_and_progress_persists_between_sessions(
    engine: Engine, clock: Clock
) -> None:
    library = make(engine, clock).get("/api/quests/library").json()
    assert 5 <= len(library) <= 8
    assert {t["kind"] for t in library} == {"quest", "challenge"}

    first = make(engine, clock, "bob@example.com")
    quest = accept(first)
    assert quest["title"]
    assert len(quest["steps"]) == 4
    assert done(first, quest["id"], 0).status_code == 200
    assert done(first, quest["id"], 1).status_code == 200

    # новый сеанс того же пользователя: прогресс на месте
    second = TestClient(create_app(engine, today=clock))
    assert second.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": PW}
    ).is_success
    mine = second.get("/api/quests").json()
    assert [s["done_on"] is not None for s in mine[0]["steps"]] == [True, True, False, False]


@pytest.mark.acceptance("kognis-99x", "AC1")
def test_accept_from_analysis_result(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    r = client.post("/api/entries", json={"text": "не хочется звонить", "date": "2026-09-01"})
    assert r.status_code == 201
    analysis = client.post(
        "/api/analyses",
        json={"direction": "cbt", "consent": True, "start": "2026-09-01", "end": "2026-09-07"},
    ).json()
    assert analysis["quest_ideas"] == ["Позвонить другу"]

    quest = client.post(
        "/api/quests/from-analysis", json={"analysis_id": analysis["id"], "idea": 0}
    )
    assert quest.status_code == 201
    body = quest.json()
    assert body["source"] == "analysis"
    assert body["title"] == "Позвонить другу"
    assert any(s["title"] == "Позвонить другу" for s in body["steps"])
    assert done(client, body["id"], 0).status_code == 200

    # та же идея второй раз, несуществующая идея и чужой анализ
    again = client.post(
        "/api/quests/from-analysis", json={"analysis_id": analysis["id"], "idea": 0}
    )
    assert again.status_code == 409
    missing = client.post(
        "/api/quests/from-analysis", json={"analysis_id": analysis["id"], "idea": 5}
    )
    assert missing.status_code == 422
    stranger = make(engine, clock, "eve@example.com")
    foreign = stranger.post(
        "/api/quests/from-analysis", json={"analysis_id": analysis["id"], "idea": 0}
    )
    assert foreign.status_code == 404


def test_blank_idea_from_analysis_is_rejected(engine: Engine, clock: Clock) -> None:
    client = TestClient(create_app(engine, today=clock, ai_provider=OneAnalysis(["   "])))
    creds = {"email": "ann@example.com", "password": PW}
    assert client.post("/api/auth/register", json=creds).status_code == 201
    client.post("/api/entries", json={"text": "просто день", "date": "2026-09-01"})
    analysis = client.post(
        "/api/analyses",
        json={"direction": "cbt", "consent": True, "start": "2026-09-01", "end": "2026-09-07"},
    ).json()
    blank = client.post(
        "/api/quests/from-analysis", json={"analysis_id": analysis["id"], "idea": 0}
    )
    assert blank.status_code == 422
    assert client.get("/api/quests").json() == []


@pytest.mark.acceptance("kognis-99x", "AC1")
def test_quests_are_isolated_between_users(engine: Engine, clock: Clock) -> None:
    ann = make(engine, clock)
    quest = accept(ann)
    eve = make(engine, clock, "eve@example.com")
    assert eve.get("/api/quests").json() == []
    assert done(eve, quest["id"], 0).status_code == 404
    assert xp(eve) == 0
    assert ann.get("/api/quests").json()[0]["steps"][0]["done_on"] is None


def test_same_quest_cannot_be_accepted_twice_until_finished(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    quest = accept(client)
    assert client.post("/api/quests", json={"template": LIBRARY_QUEST}).status_code == 409
    for idx in range(4):
        assert done(client, quest["id"], idx).status_code == 200
    accept(client)  # после завершения можно взять снова
    assert client.post("/api/quests", json={"template": "nope"}).status_code == 422


def test_bad_step_index_is_rejected(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    quest = accept(client)
    assert done(client, quest["id"], 9).status_code == 422
    assert done(client, quest["id"], -1).status_code == 422


@pytest.mark.acceptance("kognis-99x", "AC2")
def test_step_and_quest_xp_without_repeats(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    quest = accept(client)
    assert xp(client) == 0

    first = done(client, quest["id"], 0).json()
    assert first["xp"] == 15
    assert xp(client) == 15
    repeat = done(client, quest["id"], 0).json()
    assert repeat["xp"] == 0
    assert xp(client) == 15

    for idx in (1, 2):
        assert done(client, quest["id"], idx).json()["xp"] == 15
    last = done(client, quest["id"], 3).json()
    assert last["xp"] == 15 + 50  # шаг + завершение квеста
    assert last["quest"]["completed_on"] == "2026-09-01"
    assert xp(client) == 4 * 15 + 50

    assert done(client, quest["id"], 3).json()["xp"] == 0
    assert xp(client) == 4 * 15 + 50


@pytest.mark.acceptance("kognis-99x", "AC2")
def test_challenge_allows_one_step_per_day(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    challenge = accept(client, CHALLENGE)
    assert challenge["kind"] == "challenge"
    assert len(challenge["steps"]) == 5
    assert done(client, challenge["id"], 0).json()["xp"] == 15
    assert done(client, challenge["id"], 1).status_code == 409
    assert xp(client) == 15
    for idx in range(1, 5):
        clock.day += dt.timedelta(days=1)
        assert done(client, challenge["id"], idx).status_code == 200
    assert xp(client) == 5 * 15 + 50
    assert client.get("/api/quests").json()[0]["completed_on"] == "2026-09-05"


def test_quest_xp_does_not_extend_streak(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    assert done(client, accept(client)["id"], 0).status_code == 200
    body = client.get("/api/progress").json()
    assert body["xp"] == 15
    assert body["streak"] == 0


@pytest.mark.acceptance("kognis-99x", "AC3")
def test_quiz_saves_answers_and_gives_xp_once_a_day(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    quizzes = client.get("/api/quizzes").json()
    assert quizzes
    assert not any(q["done_today"] for q in quizzes)
    quiz = next(q for q in quizzes if q["code"] == "evening")

    r = client.post("/api/quizzes/evening/answers", json={"answers": ANSWERS})
    assert r.status_code == 201
    assert r.json()["xp"] == 10
    assert xp(client) == 10
    assert client.get("/api/quizzes").json()[0]["done_today"] is True

    again = client.post("/api/quizzes/evening/answers", json={"answers": ANSWERS})
    assert again.status_code == 409
    assert xp(client) == 10
    saved = client.get("/api/quizzes/evening/answers").json()
    assert saved == [{"date": "2026-09-01", "answers": ANSWERS}]
    assert len(quiz["questions"]) == len(ANSWERS)

    # другой квиз в тот же день — отдельно; тот же квиз на следующий день — снова
    other = client.post("/api/quizzes/values/answers", json={"answers": ["Работа", "Прогулка"]})
    assert other.json()["xp"] == 10
    clock.day += dt.timedelta(days=1)
    assert client.post("/api/quizzes/evening/answers", json={"answers": ANSWERS}).json()["xp"] == 10
    assert xp(client) == 30
    assert len(client.get("/api/quizzes/evening/answers").json()) == 2


def test_quiz_validation_and_isolation(engine: Engine, clock: Clock) -> None:
    ann = make(engine, clock)
    assert ann.post("/api/quizzes/evening/answers", json={"answers": ["один"]}).status_code == 422
    blank = ann.post("/api/quizzes/evening/answers", json={"answers": ["а", " ", "б"]})
    assert blank.status_code == 422
    assert ann.post("/api/quizzes/nope/answers", json={"answers": ["а"]}).status_code == 422
    assert ann.get("/api/quizzes/nope/answers").status_code == 404
    assert xp(ann) == 0
    assert ann.post("/api/quizzes/evening/answers", json={"answers": ANSWERS}).status_code == 201
    eve = make(engine, clock, "eve@example.com")
    assert eve.get("/api/quizzes/evening/answers").json() == []
    assert eve.get("/api/quizzes").json()[0]["done_today"] is False


def test_crisis_quiz_answers_saved_without_xp(engine: Engine, clock: Clock) -> None:
    client = make(engine, clock)
    crisis = ["Не хочу жить", "Ничего", "Ничего"]
    r = client.post("/api/quizzes/evening/answers", json={"answers": crisis})
    body = r.json()
    assert r.status_code == 201
    assert body["xp"] == 0
    assert body["help"]["contacts"]
    assert body["saved"]["answers"] == crisis
    assert xp(client) == 0


def test_endpoints_require_login(engine: Engine, clock: Clock) -> None:
    anon = TestClient(create_app(engine, today=clock))
    assert anon.get("/api/quests").status_code == 401
    assert anon.get("/api/quests/library").status_code == 401
    assert anon.get("/api/quizzes").status_code == 401
    assert anon.post("/api/quizzes/evening/answers", json={"answers": ANSWERS}).status_code == 401
