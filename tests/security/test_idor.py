"""IDOR (kognis-d5p): пользователь B не видит и не меняет объекты пользователя A.

Чужой объект неотличим от несуществующего (404, не 403); данные владельца не меняются.
"""

import base64
import datetime as dt
import json
from collections.abc import Sequence
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

PW = "correct horse"
LOCK_PW = "замок-12345"
PRIVATE_TEXT = "Секретная мысль про начальника"
KEY = base64.b64encode(b"K" * 32).decode()
NOON = dt.datetime(2026, 9, 1, 12, tzinfo=dt.UTC)
ANSWERS = ["Разговор с друзьями", "Получилось начать", "Начал бы раньше"]
MISSING = 999_999


class OneAnalysis:
    """Провайдер, отвечающий одним готовым анализом."""

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        return json.dumps(
            {"summary": "Неделя.", "patterns": [], "questions": ["Что помогло?"], "quest_ideas": []}
        )


def make_pair(engine: Engine) -> tuple[TestClient, TestClient]:
    """Два пользователя одного приложения, у каждого свои cookie."""
    app = create_app(engine, clock=lambda: NOON, ai_provider=OneAnalysis(), data_key=KEY)
    pair: list[TestClient] = []
    for email in ("ann@example.com", "eve@example.com"):
        client = TestClient(app)
        assert (
            client.post("/api/auth/register", json={"email": email, "password": PW}).status_code
            == 201
        )
        pair.append(client)
    return pair[0], pair[1]


@pytest.fixture
def ann_eve(engine: Engine) -> tuple[TestClient, TestClient]:
    return make_pair(engine)


def create_entry(client: TestClient, **extra: Any) -> dict[str, Any]:
    r = client.post("/api/entries", json={"text": PRIVATE_TEXT, "date": "2026-09-01", **extra})
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def create_locked(client: TestClient) -> dict[str, Any]:
    return create_entry(client, protection="locked", lock_password=LOCK_PW)


def create_analysis(client: TestClient) -> dict[str, Any]:
    create_entry(client)
    r = client.post(
        "/api/analyses",
        json={"direction": "cbt", "consent": True, "start": "2026-09-01", "end": "2026-09-07"},
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def assert_not_found(response: Any) -> None:
    assert response.status_code == 404, response.text
    assert PRIVATE_TEXT not in response.text


FORBIDDEN_KEYS = {"password", "password_hash", "hash", "lock_hash", "lock_cipher", "token"}
GET_URLS = [
    "/api/me",
    "/api/entries",
    "/api/day-reviews",
    "/api/progress",
    "/api/analyses",
    "/api/analyses/directions",
    "/api/analyses/mood?start=2026-09-01&end=2026-09-07",
    "/api/analyses/period",
    "/api/analyses/memory",
    "/api/quests",
    "/api/quests/library",
    "/api/quizzes",
    "/api/quizzes/evening/answers",
]


def keys(node: object) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in cast("dict[str, object]", node).items():
            found |= {key} | keys(value)
    elif isinstance(node, list):
        for item in cast("list[object]", node):
            found |= keys(item)
    return found


@pytest.mark.security("idor", "GET /api/entries/{entry_id}")
def test_get_entry(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    entry = create_entry(ann)
    assert_not_found(eve.get(f"/api/entries/{entry['id']}"))
    assert_not_found(eve.get(f"/api/entries/{MISSING}"))
    assert ann.get(f"/api/entries/{entry['id']}").json()["text"] == PRIVATE_TEXT


@pytest.mark.security("idor", "POST /api/entries/{entry_id}/open")
def test_open_entry(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    entry = create_locked(ann)
    assert_not_found(eve.post(f"/api/entries/{entry['id']}/open", json={"password": LOCK_PW}))
    opened = ann.post(f"/api/entries/{entry['id']}/open", json={"password": LOCK_PW})
    assert opened.json()["text"] == PRIVATE_TEXT


@pytest.mark.security("idor", "POST /api/entries/{entry_id}/lock")
def test_lock_entry(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    entry = create_entry(ann)
    assert_not_found(eve.post(f"/api/entries/{entry['id']}/lock", json={"password": LOCK_PW}))
    after = ann.get(f"/api/entries/{entry['id']}").json()
    assert after["protection"] == "plain"
    assert after["text"] == PRIVATE_TEXT


@pytest.mark.security("idor", "POST /api/entries/{entry_id}/unlock")
def test_unlock_entry(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    entry = create_locked(ann)
    assert_not_found(eve.post(f"/api/entries/{entry['id']}/unlock", json={"password": LOCK_PW}))
    assert ann.get(f"/api/entries/{entry['id']}").json()["protection"] == "locked"


@pytest.mark.security("idor", "PUT /api/day-reviews/{review_date}")
def test_day_review_is_per_user(ann_eve: tuple[TestClient, TestClient]) -> None:
    """Ключ — дата, но итог всегда принадлежит вошедшему: запись B не затрагивает итог A."""
    ann, eve = ann_eve
    url = "/api/day-reviews/2026-09-01"
    saved = ann.put(url, json={"wellbeing": 7, "mood": 8, "reflection": PRIVATE_TEXT}).json()
    assert eve.put(url, json={"wellbeing": 1, "mood": 1, "reflection": "чужое"}).status_code == 200
    assert [r["id"] for r in eve.get("/api/day-reviews").json()] != [saved["id"]]
    mine = ann.get("/api/day-reviews").json()
    assert [(r["id"], r["wellbeing"], r["mood"], r["reflection"]) for r in mine] == [
        (saved["id"], 7, 8, PRIVATE_TEXT)
    ]
    assert PRIVATE_TEXT not in eve.get("/api/day-reviews").text


@pytest.mark.security("idor", "GET /api/analyses/{analysis_id}")
def test_get_analysis(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    analysis = create_analysis(ann)
    assert eve.get(f"/api/analyses/{analysis['id']}").status_code == 404
    assert eve.get("/api/analyses").json() == []
    assert ann.get(f"/api/analyses/{analysis['id']}").status_code == 200


@pytest.mark.acceptance("kognis-qkh", "AC4")
@pytest.mark.security("idor", "DELETE /api/analyses/{analysis_id}")
def test_delete_analysis(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    analysis = create_analysis(ann)
    url = f"/api/analyses/{analysis['id']}"
    assert eve.request("DELETE", url, json={}).status_code == 404
    assert eve.request("DELETE", f"/api/analyses/{MISSING}", json={}).status_code == 404
    assert ann.get(f"/api/analyses/{analysis['id']}").status_code == 200
    assert ann.request("DELETE", url, json={}).status_code == 204
    assert ann.get(f"/api/analyses/{analysis['id']}").status_code == 404


@pytest.mark.security("idor", "POST /api/analyses/{analysis_id}/answers")
def test_answer_analysis(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    analysis = create_analysis(ann)
    before = ann.get(f"/api/analyses/{analysis['id']}").json()
    r = eve.post(
        f"/api/analyses/{analysis['id']}/answers", json={"answers": ["чужой"], "consent": True}
    )
    assert r.status_code == 404
    assert ann.get(f"/api/analyses/{analysis['id']}").json() == before
    assert len(ann.get("/api/analyses").json()) == 1


@pytest.mark.security("idor", "POST /api/quests/{quest_id}/steps/{idx}/done")
def test_quest_step_done(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    quest = ann.post("/api/quests", json={"template": "catch_thought"}).json()
    assert eve.post(f"/api/quests/{quest['id']}/steps/0/done", json={}).status_code == 404
    assert ann.get("/api/quests").json()[0]["steps"][0]["done_on"] is None
    assert eve.get("/api/progress").json()["xp"] == 0
    assert ann.get("/api/progress").json()["xp"] == 0


@pytest.mark.security("idor", "POST /api/quizzes/{code}/answers")
def test_quiz_submit_is_per_user(ann_eve: tuple[TestClient, TestClient]) -> None:
    """Код квиза — общий справочник, ответы всегда пишутся владельцу сессии."""
    ann, eve = ann_eve
    assert ann.post("/api/quizzes/evening/answers", json={"answers": ANSWERS}).status_code == 201
    assert eve.get("/api/quizzes/evening/answers").json() == []
    assert eve.post("/api/quizzes/evening/answers", json={"answers": ANSWERS}).status_code == 201
    assert len(ann.get("/api/quizzes/evening/answers").json()) == 1
    assert eve.post("/api/quizzes/nope/answers", json={"answers": ANSWERS}).status_code == 422


@pytest.mark.security("idor", "GET /api/quizzes/{code}/answers")
def test_quiz_history_is_per_user(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, eve = ann_eve
    ann.post("/api/quizzes/evening/answers", json={"answers": ANSWERS})
    assert eve.get("/api/quizzes/evening/answers").json() == []
    assert eve.get("/api/quizzes/nope/answers").status_code == 404
    assert ann.get("/api/quizzes/evening/answers").json()[0]["answers"] == ANSWERS


@pytest.mark.acceptance("kognis-d5p", "AC1")
def test_ab_scenario_owner_data_untouched(ann_eve: tuple[TestClient, TestClient]) -> None:
    """Сквозной сценарий: B пробует каждое действие над объектами A — везде 404, данные A целы."""
    ann, eve = ann_eve
    plain = create_entry(ann)
    locked = create_locked(ann)
    analysis = create_analysis(ann)
    quest = ann.post("/api/quests", json={"template": "catch_thought"}).json()
    urls = ("/api/entries", "/api/analyses", "/api/quests")
    snapshot = [ann.get(u).text for u in urls]
    lock = {"password": LOCK_PW}
    answers = {"answers": ["а"], "consent": True}

    attempts = [
        eve.get(f"/api/entries/{plain['id']}"),
        eve.post(f"/api/entries/{plain['id']}/lock", json=lock),
        eve.post(f"/api/entries/{locked['id']}/open", json=lock),
        eve.post(f"/api/entries/{locked['id']}/unlock", json=lock),
        eve.get(f"/api/analyses/{analysis['id']}"),
        eve.post(f"/api/analyses/{analysis['id']}/answers", json=answers),
        eve.request("DELETE", f"/api/analyses/{analysis['id']}", json={}),
        eve.post(f"/api/quests/{quest['id']}/steps/0/done", json={}),
        eve.post("/api/quests/from-analysis", json={"analysis_id": analysis["id"], "idea": 0}),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    assert all(PRIVATE_TEXT not in r.text for r in attempts)
    assert snapshot == [ann.get(u).text for u in urls]
    assert [eve.get(u).json() for u in urls] == [[], [], []]


@pytest.mark.acceptance("kognis-d5p", "AC2")
def test_responses_have_no_hashes_ciphertext_or_foreign_data(
    engine: Engine, ann_eve: tuple[TestClient, TestClient]
) -> None:
    ann, eve = ann_eve
    locked = create_locked(ann)
    create_entry(ann)
    create_analysis(ann)
    review = {"wellbeing": 7, "mood": 8, "reflection": PRIVATE_TEXT}
    ann.put("/api/day-reviews/2026-09-01", json=review)
    ann.post("/api/quests", json={"template": "catch_thought"})
    ann.post("/api/quizzes/evening/answers", json={"answers": ANSWERS})
    token = ann.cookies.get("kognis_session")
    assert token
    with engine.connect() as conn:
        user = conn.execute(sql("SELECT * FROM users")).mappings().first()
        entry = conn.execute(
            sql("SELECT lock_hash, lock_cipher FROM entries WHERE lock_hash IS NOT NULL")
        ).one()
        sessions = conn.execute(sql("SELECT * FROM sessions")).all()
    assert user
    forbidden = {token, *(str(v) for v in entry), *(str(v) for row in sessions for v in row)}
    for value in entry:  # шифртекст — bytes: str(bytes) в JSON не встретится, ищем реальные формы
        if isinstance(value, bytes):
            raw = value
            forbidden |= {base64.b64encode(raw).decode(), raw.hex(), raw.decode("latin-1")}
    public_columns = {"id", "email", "advanced", "timezone"}
    forbidden |= {str(v) for k, v in user.items() if k not in public_columns}

    for url in [*GET_URLS, f"/api/entries/{locked['id']}"]:
        response = ann.get(url)
        assert response.status_code == 200, url
        assert not keys(response.json()) & FORBIDDEN_KEYS, url
        assert not any(len(s) > 8 and s in response.text for s in forbidden), url
    for url in GET_URLS:  # у B нет ничего от A
        body = eve.get(url).text
        assert PRIVATE_TEXT not in body, url
        assert "ann@example.com" not in body, url


@pytest.mark.acceptance("kognis-sky", "AC5")
@pytest.mark.security("idor", "GET /api/analyses/memory")
@pytest.mark.security("idor", "DELETE /api/analyses/memory")
def test_ai_memory_is_private(ann_eve: tuple[TestClient, TestClient], engine: Engine) -> None:
    """Память ИИ привязана к владельцу: чужая не читается и не очищается (маршруты без id)."""
    ann, eve = ann_eve
    ann_id = ann.get("/api/me").json()["id"]
    with engine.begin() as conn:
        conn.execute(
            sql("INSERT INTO analysis_memory (owner_id, digest, updated_at) VALUES (:o, :d, :t)"),
            {"o": ann_id, "d": PRIVATE_TEXT, "t": "2026-09-01 10:00:00"},
        )
    assert ann.get("/api/analyses/memory").json()["digest"] == PRIVATE_TEXT
    assert eve.get("/api/analyses/memory").json() == {"digest": "", "updated_at": None}
    assert eve.request("DELETE", "/api/analyses/memory", json={}).status_code == 204
    assert ann.get("/api/analyses/memory").json()["digest"] == PRIVATE_TEXT  # у владельца цела


@pytest.mark.acceptance("kognis-d5p", "AC3")
def test_oversized_body_and_lists_are_rejected(ann_eve: tuple[TestClient, TestClient]) -> None:
    ann, _ = ann_eve
    json_type = {"content-type": "application/json"}
    assert ann.post("/api/entries", json={"text": "я" * 2_000_000}).status_code == 413
    chunks = iter([b'{"text": "', b"x" * 2_000_000, b'"}'])  # без Content-Length
    assert ann.post("/api/entries", content=chunks, headers=json_type).status_code == 413
    tags = [f"т{i}" for i in range(500)]
    assert ann.post("/api/entries", json={"text": "а", "tags": tags}).status_code == 422
    assert ann.post("/api/entries", json={"text": "а" * 20_001}).status_code == 422
    quiz = ann.post("/api/quizzes/evening/answers", json={"answers": ["а"] * 1000})
    assert quiz.status_code == 422
    review = {"wellbeing": 5, "mood": 5, "reflection": "а" * 6000}
    assert ann.put("/api/day-reviews/2026-09-01", json=review).status_code == 422
    assert ann.get("/api/entries").json() == []  # сервер жив, ничего не сохранилось
    assert ann.get("/health").status_code == 200
