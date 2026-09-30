"""Анализ периода: приёмочные тесты kognis-kai (AC1–AC5) через HTTP API и юнит-тесты правил."""

import datetime as dt
import json
from collections.abc import Sequence
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from kognis.access import Feature, can_use
from kognis.ai import AiError, Message
from kognis.analysis import AnalysisResult, MoodPoint
from kognis.analysis._domain import mood_dynamics
from kognis.safety import DISCLAIMER
from kognis.web import create_app

PW = "correct horse"
PERIOD = {"start": "2026-09-01", "end": "2026-09-07"}
ENTRY_TEXT = "не хочется звонить заказчику"


class ScriptedProvider:
    """Отвечает по очереди заготовленными ответами и запоминает все вызовы."""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, list[Message]]] = []

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        self.calls.append((system, list(messages)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def good(entry_ids: list[int]) -> str:
    return json.dumps(
        {
            "summary": "Неделя прошла с тревогой перед работой.",
            "patterns": [
                {
                    "title": "Избегание",
                    "description": "Откладываешь неприятные задачи.",
                    "entry_ids": entry_ids,
                    "quotes": ["не хочется звонить"],
                }
            ],
            "questions": ["Что помогло бы начать?"],
            "quest_ideas": ["Позвонить одному человеку"],
        }
    )


def make(engine: Engine, provider: ScriptedProvider, email: str = "ann@example.com") -> TestClient:
    client = TestClient(create_app(engine, ai_provider=provider))
    r = client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return client


def add_entry(client: TestClient, text: str = ENTRY_TEXT, day: str = "2026-09-02") -> int:
    r = client.post("/api/entries", json={"text": text, "date": day})
    assert r.status_code == 201
    return int(r.json()["id"])


def analyze(client: TestClient, consent: bool = True, direction: str = "cbt") -> Any:
    return client.post("/api/analyses", json={"direction": direction, "consent": consent, **PERIOD})


def first_analysis(client: TestClient, provider: ScriptedProvider) -> dict[str, Any]:
    eid = add_entry(client)
    provider.replies.append(good([eid]))
    body: dict[str, Any] = analyze(client).json()
    return body


@pytest.mark.acceptance("kognis-kai", "AC1")
def test_without_consent_provider_is_not_called(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    add_entry(client)
    for extra in ({}, {"consent": False}):
        r = client.post("/api/analyses", json={"direction": "cbt", **PERIOD, **extra})
        assert r.status_code == 403
    assert provider.calls == []
    assert client.get("/api/analyses").json() == []


@pytest.mark.acceptance("kognis-kai", "AC1")
def test_answers_without_consent_not_sent(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    first = first_analysis(client, provider)
    r = client.post(f"/api/analyses/{first['id']}/answers", json={"answers": ["страшно"]})
    assert r.status_code == 403
    assert len(provider.calls) == 1


@pytest.mark.acceptance("kognis-kai", "AC1")
def test_only_period_entries_are_sent(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client, "обычная запись про работу")
    add_entry(client, "запись вне периода", day="2026-08-01")
    provider.replies.append(good([eid]))
    assert analyze(client).status_code == 201
    sent = provider.calls[0][1][0].content
    assert "обычная запись про работу" in sent
    assert "вне периода" not in sent


@pytest.mark.acceptance("kognis-kai", "AC1")
def test_protected_entries_never_sent(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client, "обычная запись про работу")
    secret_id = add_entry(client, "секрет под замком")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE entries SET protection = 'locked' WHERE id = :i"), {"i": secret_id}
        )
    provider.replies.append(good([eid]))
    assert analyze(client).status_code == 201
    sent = provider.calls[0][1][0].content
    assert "обычная запись" in sent
    assert "секрет" not in sent
    # кризисный флаг защищённой записи всё равно даёт поддержку, а не анализ
    with engine.begin() as conn:
        conn.execute(text("UPDATE entries SET crisis = 1 WHERE id = :i"), {"i": secret_id})
    assert analyze(client).json()["status"] == "crisis"
    assert len(provider.calls) == 1


@pytest.mark.acceptance("kognis-kai", "AC2")
def test_analysis_returns_and_saves_result(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client)
    provider.replies.append(good([eid]))
    r = analyze(client, direction="act")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "done"
    assert body["summary"]
    assert body["patterns"][0]["entry_ids"] == [eid]
    assert body["questions"] == ["Что помогло бы начать?"]
    assert "ACT" in provider.calls[0][0]
    history = client.get("/api/analyses").json()
    assert [a["id"] for a in history] == [body["id"]]
    assert client.get(f"/api/analyses/{body['id']}").json()["summary"] == body["summary"]


@pytest.mark.acceptance("kognis-kai", "AC2")
def test_follow_up_answers_continue_analysis(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    first = first_analysis(client, provider)
    provider.replies.append(good([1]))
    r = client.post(
        f"/api/analyses/{first['id']}/answers",
        json={"answers": ["Боюсь отказа"], "consent": True},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["parent_id"] == first["id"]
    assert body["answers"] == ["Боюсь отказа"]
    assert "Боюсь отказа" in provider.calls[1][1][0].content
    assert len(client.get("/api/analyses").json()) == 2


@pytest.mark.acceptance("kognis-kai", "AC2")
def test_other_users_analysis_is_not_found(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    analysis_id = first_analysis(client, provider)["id"]
    other = make(engine, provider, "bob@example.com")
    assert other.get(f"/api/analyses/{analysis_id}").status_code == 404
    r = other.post(f"/api/analyses/{analysis_id}/answers", json={"answers": ["x"], "consent": True})
    assert r.status_code == 404
    assert other.get("/api/analyses").json() == []


@pytest.mark.acceptance("kognis-kai", "AC2")
def test_feature_gate_and_no_data(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    assert analyze(client).status_code == 422  # записей за период нет
    assert can_use(1, Feature.AI_ANALYSIS)

    def deny(user_id: int, feature: Feature) -> bool:
        return False

    monkeypatch.setattr("kognis.web._analysis.can_use", deny)
    assert analyze(client).status_code == 403
    assert provider.calls == []


@pytest.mark.acceptance("kognis-kai", "AC3")
def test_invalid_answer_is_retried_once(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client)
    provider.replies += ["это не JSON", good([eid])]
    assert analyze(client).status_code == 201
    assert len(provider.calls) == 2


@pytest.mark.acceptance("kognis-kai", "AC3")
@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        json.dumps({"summary": "x"}),
        json.dumps({"summary": "x", "patterns": [], "questions": [], "лишнее": 1}),
        good([999]),  # опора на несуществующую запись
    ],
)
def test_invalid_answers_give_clear_error_and_app_lives(engine: Engine, bad: str) -> None:
    provider = ScriptedProvider(bad, bad)
    client = make(engine, provider)
    add_entry(client)
    r = analyze(client)
    assert r.status_code == 502
    assert r.json()["detail"] == {"code": "analysis.bad_answer", "params": {}}
    assert client.get("/api/analyses").json() == []
    assert client.get("/api/me").status_code == 200


@pytest.mark.acceptance("kognis-kai", "AC3")
def test_provider_error_gives_clear_message(engine: Engine) -> None:
    provider = ScriptedProvider(AiError("ai.http_server", status=500))
    client = make(engine, provider)
    add_entry(client)
    r = analyze(client)
    assert r.status_code == 502
    assert r.json()["detail"] == {"code": "ai.http_server", "params": {"status": 500}}


@pytest.mark.acceptance("kognis-kai", "AC4")
def test_crisis_entry_gives_support_without_patterns_or_provider(
    engine: Engine, crisis_on: None
) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    add_entry(client, "Сегодня я не хочу больше жить")
    add_entry(client, "обычная запись")
    r = analyze(client, consent=False)  # поддержка не зависит от согласия
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "crisis"
    assert body["patterns"] == []
    assert body["summary"] is None
    assert body["help"]["contacts"][0]["phone"] == "112"
    assert provider.calls == []


@pytest.mark.acceptance("kognis-kai", "AC4")
def test_crisis_in_day_review_reflection(engine: Engine, crisis_on: None) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    add_entry(client, "обычная запись")
    client.put(
        "/api/day-reviews/2026-09-03",
        json={"wellbeing": 2, "mood": 2, "reflection": "хочу умереть"},
    )
    body = analyze(client).json()
    assert body["status"] == "crisis"
    assert body["help"] is not None
    assert provider.calls == []


@pytest.mark.acceptance("kognis-kai", "AC4")
def test_crisis_in_follow_up_answer(engine: Engine, crisis_on: None) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    first = first_analysis(client, provider)
    r = client.post(
        f"/api/analyses/{first['id']}/answers", json={"answers": ["жить не хочу"], "consent": True}
    )
    assert r.json()["status"] == "crisis"
    assert r.json()["patterns"] == []
    assert len(provider.calls) == 1


@pytest.mark.acceptance("kognis-kai", "AC5")
def test_mood_dynamics_computed_locally(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    for day, mood in (("2026-09-01", 3), ("2026-09-02", 4), ("2026-09-05", 7), ("2026-09-06", 8)):
        client.put(f"/api/day-reviews/{day}", json={"wellbeing": mood, "mood": mood})
    client.put("/api/day-reviews/2026-08-01", json={"wellbeing": 1, "mood": 1})  # вне периода
    body = client.get("/api/analyses/mood", params=PERIOD).json()
    assert [p["mood"] for p in body["points"]] == [3, 4, 7, 8]
    assert body["average_mood"] == 5.5
    assert body["trend"] == "up"
    assert provider.calls == []


@pytest.mark.acceptance("kognis-kai", "AC5")
def test_mood_trend_rules() -> None:
    day = dt.date(2026, 9, 1)

    def trend(moods: list[int]) -> str:
        pts = [MoodPoint(day + dt.timedelta(i), m, m) for i, m in enumerate(moods)]
        return mood_dynamics(pts).trend

    assert trend([]) == "unknown"
    assert trend([5]) == "unknown"
    assert trend([5, 5, 5, 5]) == "flat"
    assert trend([8, 7, 3, 2]) == "down"
    assert mood_dynamics([]).average_mood is None


def test_period_and_direction_validation(engine: Engine) -> None:
    client = make(engine, ScriptedProvider())
    for start, end in (("2026-09-07", "2026-09-01"), ("2026-01-01", "2026-09-01")):
        r = client.post(
            "/api/analyses",
            json={"direction": "cbt", "consent": True, "start": start, "end": end},
        )
        assert r.status_code == 422
    assert analyze(client, direction="nope").status_code == 422
    directions = client.get("/api/analyses/directions").json()
    assert len(directions) == 5
    assert directions[0]["code"] == "cbt"


def test_day_reviews_are_sent_with_entries(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client)
    client.put(
        "/api/day-reviews/2026-09-03",
        json={"wellbeing": 4, "mood": 5, "reflection": "устал, но доволен"},
    )
    provider.replies.append(good([eid]))
    assert analyze(client).status_code == 201
    assert "устал, но доволен" in provider.calls[0][1][0].content


def test_follow_up_errors(engine: Engine, crisis_on: None) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    first = first_analysis(client, provider)
    url = f"/api/analyses/{first['id']}/answers"
    assert client.post(url, json={"answers": ["  "], "consent": True}).status_code == 422
    assert client.post(url, json={"answers": ["я" * 3000], "consent": True}).status_code == 422
    provider.replies += ["мусор", "мусор"]
    assert client.post(url, json={"answers": ["ок"], "consent": True}).status_code == 502
    # кризисный анализ продолжать нельзя
    crisis = make(engine, provider, "eve@example.com")
    add_entry(crisis, "хочу умереть")
    crisis_id = analyze(crisis).json()["id"]
    r = crisis.post(f"/api/analyses/{crisis_id}/answers", json={"answers": ["ок"], "consent": True})
    assert r.status_code == 422


def test_mood_rejects_bad_period(engine: Engine) -> None:
    client = make(engine, ScriptedProvider())
    r = client.get("/api/analyses/mood", params={"start": "2026-09-07", "end": "2026-09-01"})
    assert r.status_code == 422


def _example_from_prompt(prompt: str) -> Any:
    start = prompt.index("{", prompt.index("образец"))
    example, _ = json.JSONDecoder().raw_decode(prompt[start:])
    return example


def _schema_keys(schema: dict[str, Any], node: dict[str, Any]) -> Any:
    """Дерево ключей по JSON-схеме: словарь для объектов, список из одного элемента для массивов."""
    if "$ref" in node:
        return _schema_keys(schema, schema["$defs"][node["$ref"].split("/")[-1]])
    if node.get("type") == "array":
        return [_schema_keys(schema, node["items"])]
    if node.get("type") == "object":
        props: dict[str, dict[str, Any]] = node["properties"]
        return {k: _schema_keys(schema, v) for k, v in props.items()}
    return node["type"]


def _example_keys(node: Any) -> Any:
    if isinstance(node, dict):
        fields = cast("dict[str, Any]", node)
        return {k: _example_keys(v) for k, v in fields.items()}
    if isinstance(node, list):
        return [_example_keys(cast("list[Any]", node)[0])]
    return "integer" if isinstance(node, int) else "string"


@pytest.mark.acceptance("kognis-149", "AC1")
def test_prompt_example_matches_schema(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    provider.replies.append(good([add_entry(client)]))
    assert analyze(client).status_code == 201
    example = _example_from_prompt(provider.calls[0][0])
    AnalysisResult.model_validate(example)
    schema = AnalysisResult.model_json_schema()
    assert _example_keys(example) == _schema_keys(schema, schema)
    assert "не объекты" in provider.calls[0][0]


@pytest.mark.acceptance("kognis-149", "AC2")
def test_retry_sends_errors_and_previous_answer(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client)
    pattern = {"name": "x", "entry_ids": [eid], "quotes": [{"entry_id": eid, "quote": ENTRY_TEXT}]}
    bad = json.dumps({"summary": "s", "patterns": [pattern], "questions": []})
    provider.replies += [bad, good([eid])]
    r = analyze(client)
    assert r.status_code == 201
    assert r.json()["patterns"][0]["title"] == "Избегание"
    assert len(provider.calls) == 2
    second = provider.calls[1][1]
    assert second[0] == provider.calls[0][1][0]
    assert (second[1].role, second[1].content) == ("assistant", bad)
    fix = second[2].content
    assert second[2].role == "user"
    for path in ("patterns.0.title", "patterns.0.description", "patterns.0.name"):
        assert path in fix
    assert ENTRY_TEXT not in fix
    assert len(client.get("/api/analyses").json()) == 1


@pytest.mark.acceptance("kognis-149", "AC3")
def test_two_invalid_answers_give_clear_error(engine: Engine) -> None:
    provider = ScriptedProvider("не JSON", json.dumps({"summary": "x"}))
    client = make(engine, provider)
    add_entry(client)
    r = analyze(client)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "analysis.bad_answer"
    assert len(provider.calls) == 2
    assert client.get("/api/analyses").json() == []


@pytest.mark.acceptance("kognis-149", "AC4")
def test_prompt_does_not_ask_for_disclaimer(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    provider.replies.append(good([add_entry(client)]))
    r = analyze(client)
    assert r.status_code == 201
    assert DISCLAIMER not in provider.calls[0][0]
    assert DISCLAIMER not in r.json()["summary"]


def test_retry_limits_echo_and_error_lengths(engine: Engine) -> None:
    provider = ScriptedProvider()
    client = make(engine, provider)
    eid = add_entry(client)
    junk = {f"k{i}_" + "x" * 300: i for i in range(40)}
    bad = json.dumps({"summary": "s", "patterns": [], "questions": [], **junk})
    provider.replies += [bad + " " * 20000, good([eid])]
    assert analyze(client).status_code == 201
    second = provider.calls[1][1]
    assert len(second[1].content) <= 8000
    lines = [ln for ln in second[2].content.splitlines() if ln.startswith("- ")]
    assert 0 < len(lines) <= 20
    assert all(len(ln) <= 202 for ln in lines)
