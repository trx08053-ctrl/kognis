"""Преемственность разборов (kognis-sky): период, лимиты, дубли, память — через HTTP API."""

import datetime as dt
import json
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from kognis.ai import Message
from kognis.web import create_app

PW = "correct horse"
TODAY = dt.date(2026, 9, 30)
NOW = dt.datetime(2026, 9, 30, 12, 0, tzinfo=dt.UTC)
MEMORY = "Избегает звонков; пробовал делать по одному звонку в день."


class Scripted:
    """Отвечает разбором по данным запроса и запоминает полезную нагрузку каждого вызова."""

    def __init__(self, memory: str = MEMORY, changes: Sequence[str] = ()) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.memory = memory
        self.changes = list(changes)

    def complete(
        self, system: str, messages: Sequence[Message], schema: dict[str, Any] | None = None
    ) -> str:
        data = json.loads(messages[0].content)
        self.payloads.append(data)
        ids = [e["id"] for e in data.get("entries", [])][:20]
        patterns = [
            {"title": "Избегание", "description": "Откладываешь.", "entry_ids": ids, "quotes": []}
        ]
        return json.dumps(
            {
                "summary": f"Резюме {len(self.payloads)}",
                "patterns": patterns if ids else [],
                "questions": [],
                "changes": self.changes,
                "memory": self.memory,
            }
        )


def make(engine: Engine, provider: Scripted, email: str = "ann@example.com") -> TestClient:
    client = TestClient(create_app(engine, clock=lambda: NOW, ai_provider=provider))
    r = client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return client


def add_entry(client: TestClient, day: dt.date, body: str = "не хочется звонить") -> int:
    r = client.post("/api/entries", json={"text": body, "date": day.isoformat()})
    assert r.status_code == 201
    return int(r.json()["id"])


def analyze(client: TestClient, start: dt.date, end: dt.date, direction: str = "cbt") -> Any:
    return client.post(
        "/api/analyses",
        json={"direction": direction, "start": str(start), "end": str(end), "consent": True},
    )


def period(client: TestClient) -> dict[str, Any]:
    r = client.get("/api/analyses/period")
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    return body


def done_analysis(client: TestClient, start: dt.date, end: dt.date, entry_day: dt.date) -> int:
    add_entry(client, entry_day)
    r = analyze(client, start, end)
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


@pytest.mark.acceptance("kognis-sky", "AC1")
def test_default_period_without_analyses_is_last_seven_days(engine: Engine) -> None:
    client = make(engine, Scripted())
    assert period(client) == {
        "start": "2026-09-24",
        "end": "2026-09-30",
        "active": True,
        "truncated": False,
        "last_analysis_id": None,
    }


@pytest.mark.acceptance("kognis-sky", "AC1")
def test_default_period_starts_the_day_after_last_analysis(engine: Engine) -> None:
    client = make(engine, Scripted())
    last = done_analysis(client, dt.date(2026, 9, 20), dt.date(2026, 9, 29), dt.date(2026, 9, 25))
    # с прошлого разбора новых записей нет — разбор неактивен
    assert period(client) == {
        "start": "2026-09-30",
        "end": "2026-09-30",
        "active": False,
        "truncated": False,
        "last_analysis_id": last,
    }
    add_entry(client, TODAY)
    assert period(client)["active"] is True


@pytest.mark.acceptance("kognis-sky", "AC1")
def test_default_period_is_capped_at_31_days_when_analysis_is_old(engine: Engine) -> None:
    client = make(engine, Scripted())
    done_analysis(client, dt.date(2026, 8, 15), dt.date(2026, 8, 21), dt.date(2026, 8, 16))
    add_entry(client, dt.date(2026, 9, 10))
    p = period(client)  # с 22 августа прошло 40 дней
    assert (p["start"], p["end"], p["truncated"], p["active"]) == (
        "2026-08-31",
        "2026-09-30",
        True,
        True,
    )


@pytest.mark.acceptance("kognis-sky", "AC1")
def test_default_period_when_last_analysis_ended_today_is_inactive(engine: Engine) -> None:
    client = make(engine, Scripted())
    done_analysis(client, dt.date(2026, 9, 24), TODAY, dt.date(2026, 9, 26))
    add_entry(client, TODAY)
    p = period(client)
    assert (p["start"], p["end"], p["active"]) == ("2026-09-30", "2026-09-30", False)


@pytest.mark.acceptance("kognis-sky", "AC2")
def test_period_longer_than_31_days_is_rejected(engine: Engine) -> None:
    provider = Scripted()
    client = make(engine, provider)
    add_entry(client, dt.date(2026, 9, 1))
    start = dt.date(2026, 8, 1)
    r = analyze(client, start, start + dt.timedelta(days=31))  # 32 дня
    assert r.status_code == 422
    assert r.json()["detail"] == {"code": "analysis.period_long", "params": {"max": 31}}
    assert provider.payloads == []
    assert analyze(client, dt.date(2026, 8, 31), TODAY).status_code == 201  # ровно 31 день


@pytest.mark.acceptance("kognis-sky", "AC2")
def test_text_budget_is_enforced_deterministically(engine: Engine) -> None:
    provider = Scripted()
    client = make(engine, provider)
    day = dt.date(2026, 9, 10)
    long_body = "а" * 2_000
    for _ in range(20):  # 20 × 1 500 после обрезки = 30 000 > бюджета 24 000
        add_entry(client, day, long_body)
    add_entry(client, day, "короткая запись")
    assert analyze(client, dt.date(2026, 9, 1), TODAY).status_code == 201
    entries = provider.payloads[0]["entries"]
    lengths = [len(e["text"]) for e in entries]
    assert sum(lengths) <= 24_000
    assert max(lengths) <= 1_500
    short = next(e for e in entries if e["text"].startswith("короткая"))
    assert short["text"] == "короткая запись"  # короткие остаются целыми
    assert all(e["text"].endswith("…") for e in entries if e is not short)
    # тот же вход даёт тот же результат
    second = Scripted()
    other = make(engine, second, "bob@example.com")
    for _ in range(20):
        add_entry(other, day, long_body)
    add_entry(other, day, "короткая запись")
    assert analyze(other, dt.date(2026, 9, 1), TODAY).status_code == 201
    assert [len(e["text"]) for e in second.payloads[0]["entries"]] == lengths


@pytest.mark.acceptance("kognis-sky", "AC3")
def test_repeating_direction_and_period_is_a_conflict(engine: Engine) -> None:
    provider = Scripted()
    client = make(engine, provider)
    add_entry(client, dt.date(2026, 9, 2))
    first = analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7))
    assert first.status_code == 201
    again = analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7))
    assert again.status_code == 409
    assert again.json()["detail"] == {
        "code": "analysis.duplicate",
        "params": {"existing_id": first.json()["id"]},
    }
    assert len(provider.payloads) == 1
    # другое направление или другой период — не дубль
    assert analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7), "act").status_code == 201
    assert analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 8)).status_code == 201


def test_crisis_flag_wins_over_duplicate_check(engine: Engine) -> None:
    provider = Scripted()
    client = make(engine, provider)
    entry_id = add_entry(client, dt.date(2026, 9, 2))
    assert analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7)).status_code == 201
    with engine.begin() as conn:
        conn.execute(text("UPDATE entries SET crisis = 1 WHERE id = :i"), {"i": entry_id})
    again = analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7))
    assert again.status_code == 201
    assert again.json()["status"] == "crisis"
    assert len(provider.payloads) == 1


@pytest.mark.acceptance("kognis-sky", "AC4")
def test_second_analysis_gets_memory_and_previous_result_not_old_entries(engine: Engine) -> None:
    provider = Scripted(changes=["Стало меньше избегания"])
    client = make(engine, provider)
    add_entry(client, dt.date(2026, 9, 2), "СТАРАЯ запись первой недели")
    first = analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7))
    assert first.status_code == 201
    assert "memory" not in provider.payloads[0]  # у первого разбора памяти ещё нет
    add_entry(client, dt.date(2026, 9, 9), "новая запись второй недели")
    second = analyze(client, dt.date(2026, 9, 8), dt.date(2026, 9, 14))
    assert second.status_code == 201
    sent = provider.payloads[1]
    assert sent["memory"] == MEMORY
    assert "Резюме 1" in sent["previous_analysis"]
    assert "Избегание" in sent["previous_analysis"]
    assert [e["text"] for e in sent["entries"]] == ["новая запись второй недели"]
    assert "СТАРАЯ" not in json.dumps(sent, ensure_ascii=False)
    assert len(sent["memory"]) + len(sent["previous_analysis"]) <= 3_500
    assert second.json()["changes"] == ["Стало меньше избегания"]


@pytest.mark.acceptance("kognis-sky", "AC4")
def test_memory_and_previous_result_are_capped(engine: Engine) -> None:
    provider = Scripted(memory="п" * 2_000)
    client = make(engine, provider)
    add_entry(client, dt.date(2026, 9, 2))
    assert analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7)).status_code == 201
    add_entry(client, dt.date(2026, 9, 9))
    assert analyze(client, dt.date(2026, 9, 8), dt.date(2026, 9, 14)).status_code == 201
    sent = provider.payloads[1]
    assert len(sent["memory"]) <= 2_000
    assert len(sent["previous_analysis"]) <= 1_500


@pytest.mark.acceptance("kognis-sky", "AC5")
def test_memory_is_saved_shown_and_cleared_by_the_owner_only(engine: Engine) -> None:
    ann = make(engine, Scripted())
    bob = make(engine, Scripted(), "bob@example.com")
    assert ann.get("/api/analyses/memory").json() == {"digest": "", "updated_at": None}
    add_entry(ann, dt.date(2026, 9, 2))
    assert analyze(ann, dt.date(2026, 9, 1), dt.date(2026, 9, 7)).status_code == 201
    shown = ann.get("/api/analyses/memory").json()
    assert shown["digest"] == MEMORY
    assert shown["updated_at"]
    # дайджест не хранится в самом разборе и не показывается через него
    analysis_id = ann.get("/api/analyses").json()[0]["id"]
    assert MEMORY not in ann.get(f"/api/analyses/{analysis_id}").text
    # чужой видит свою (пустую) память и не может очистить чужую
    assert bob.get("/api/analyses/memory").json()["digest"] == ""
    assert bob.request("DELETE", "/api/analyses/memory", json={}).status_code == 204
    assert ann.get("/api/analyses/memory").json()["digest"] == MEMORY
    assert ann.request("DELETE", "/api/analyses/memory", json={}).status_code == 204
    assert ann.get("/api/analyses/memory").json()["digest"] == ""


@pytest.mark.acceptance("kognis-sky", "AC5")
def test_cleared_memory_is_not_sent_and_deleting_last_analysis_clears_it(engine: Engine) -> None:
    provider = Scripted()
    client = make(engine, provider)
    add_entry(client, dt.date(2026, 9, 2))
    first_id = analyze(client, dt.date(2026, 9, 1), dt.date(2026, 9, 7)).json()["id"]
    client.request("DELETE", "/api/analyses/memory", json={})
    add_entry(client, dt.date(2026, 9, 9))
    second_id = analyze(client, dt.date(2026, 9, 8), dt.date(2026, 9, 14)).json()["id"]
    assert "memory" not in provider.payloads[1]  # очищенное не уходит модели
    assert client.get("/api/analyses/memory").json()["digest"] == MEMORY  # второй разбор её обновил
    client.request("DELETE", f"/api/analyses/{first_id}", json={})
    assert client.get("/api/analyses/memory").json()["digest"] == MEMORY
    client.request("DELETE", f"/api/analyses/{second_id}", json={})
    assert client.get("/api/analyses/memory").json()["digest"] == ""


def test_old_result_without_new_fields_is_still_readable(engine: Engine) -> None:
    client = make(engine, Scripted())
    old: dict[str, Any] = {
        "summary": "Старый разбор",
        "patterns": [],
        "questions": [],
        "quest_ideas": [],
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO analyses (owner_id, direction, period_start, period_end, status,"
                " result, answers, created_at) VALUES (1, 'cbt', '2026-09-01', '2026-09-07',"
                " 'done', :r, '[]', '2026-09-08 10:00:00')"
            ),
            {"r": json.dumps(old)},
        )
    body = client.get("/api/analyses/1").json()
    assert body["summary"] == "Старый разбор"
    assert body["changes"] == []
