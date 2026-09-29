"""Постраничная выдача записей и итогов по HTTP: приёмочные тесты kognis-3mh (AC1, AC2)."""

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient

VALID_PW = "correct horse"
NEXT = "X-Next-Cursor"


def signup(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/register", json={"email": email, "password": VALID_PW})
    assert response.status_code == 201


def add_entry(client: TestClient, text: str, day: str, **extra: object) -> int:
    response = client.post("/api/entries", json={"text": text, "date": day, **extra})
    assert response.status_code == 201
    return int(response.json()["id"])


def walk(client: TestClient, url: str, **params: str | int) -> list[list[dict[str, Any]]]:
    """Пройти все страницы по курсору из заголовка; вернуть список страниц."""
    pages: list[list[dict[str, Any]]] = []
    cursor: str | None = None
    while True:
        query: dict[str, str | int] = {**params, **({"cursor": cursor} if cursor else {})}
        response = client.get(url, params=query)
        assert response.status_code == 200
        pages.append(response.json())
        cursor = response.headers.get(NEXT)
        if cursor is None:
            return pages


@pytest.mark.acceptance("kognis-3mh", "AC1")
def test_entries_paged_without_gaps_or_repeats(client: TestClient) -> None:
    signup(client, "ann@example.com")
    ids = [add_entry(client, f"запись {n}", f"2026-08-{1 + n % 5:02d}") for n in range(45)]

    pages = walk(client, "/api/entries", limit=10)
    assert [len(p) for p in pages] == [10, 10, 10, 10, 5]
    seen = [e["id"] for page in pages for e in page]
    assert sorted(seen) == sorted(ids)  # ни пропусков, ни повторов
    order = [(e["date"], e["id"]) for page in pages for e in page]
    assert order == sorted(order, reverse=True)  # новые первыми

    default = client.get("/api/entries")
    assert len(default.json()) == 30  # по умолчанию 30
    assert default.headers[NEXT]


@pytest.mark.acceptance("kognis-3mh", "AC1")
def test_new_entry_between_pages_does_not_shift_next_page(client: TestClient) -> None:
    signup(client, "ann@example.com")
    for n in range(6):
        add_entry(client, f"запись {n}", f"2026-08-{n + 1:02d}")
    first = client.get("/api/entries", params={"limit": 3})
    add_entry(client, "свежая", "2026-09-01")  # появилась после первой страницы
    second = client.get("/api/entries", params={"limit": 3, "cursor": first.headers[NEXT]})
    assert [e["text"] for e in first.json() + second.json()] == [
        f"запись {n}" for n in (5, 4, 3, 2, 1, 0)
    ]
    assert NEXT not in second.headers


@pytest.mark.acceptance("kognis-3mh", "AC1")
def test_page_size_limits_and_bad_cursor(client: TestClient) -> None:
    signup(client, "ann@example.com")
    add_entry(client, "раз", "2026-08-01")
    assert client.get("/api/entries", params={"limit": 100}).status_code == 200
    for bad in (0, 101, -1):
        assert client.get("/api/entries", params={"limit": bad}).status_code == 422
        assert client.get("/api/day-reviews", params={"limit": bad}).status_code == 422
    for cursor in ("мусор", "2026-08-01", "2026-13-40.1", "2026-08-01.x", "2026-08-01.-5"):
        assert client.get("/api/entries", params={"cursor": cursor}).status_code == 422
    for cursor in ("мусор", "2026-08-01.3"):
        assert client.get("/api/day-reviews", params={"cursor": cursor}).status_code == 422


@pytest.mark.acceptance("kognis-3mh", "AC1")
def test_day_reviews_paged(client: TestClient) -> None:
    signup(client, "ann@example.com")
    start = dt.date(2026, 7, 1)
    for n in range(35):
        day = start + dt.timedelta(days=n)
        assert (
            client.put(
                f"/api/day-reviews/{day}", json={"wellbeing": 5, "mood": 5, "reflection": str(n)}
            ).status_code
            == 200
        )
    pages = walk(client, "/api/day-reviews", limit=12)
    assert [len(p) for p in pages] == [12, 12, 11]
    dates = [r["date"] for page in pages for r in page]
    assert dates == [str(start + dt.timedelta(days=n)) for n in reversed(range(35))]
    assert len(client.get("/api/day-reviews").json()) == 30


@pytest.mark.acceptance("kognis-3mh", "AC1")
def test_pages_show_only_own_entries(client: TestClient) -> None:
    signup(client, "ann@example.com")
    add_entry(client, "моя", "2026-08-01")
    other = TestClient(client.app)
    signup(other, "bob@example.com")
    add_entry(other, "чужая", "2026-08-02")
    assert [e["text"] for page in walk(client, "/api/entries", limit=1) for e in page] == ["моя"]


@pytest.mark.acceptance("kognis-3mh", "AC2")
def test_filters_on_server_with_pages(client: TestClient) -> None:
    signup(client, "ann@example.com")
    for n in range(12):
        day = f"2026-08-{n + 1:02d}"
        tags = ["работа"] if n % 2 == 0 else ["дом"]
        emotions = ["тревога"] if n % 3 == 0 else ["радость"]
        add_entry(client, f"запись {n}", day, tags=tags, emotions=emotions)

    work = [e for p in walk(client, "/api/entries", tag="работа", limit=2) for e in p]
    assert [e["text"] for e in work] == [f"запись {n}" for n in (10, 8, 6, 4, 2, 0)]
    assert all("работа" in e["tags"] for e in work)

    anxious = [e for p in walk(client, "/api/entries", emotion="тревога", limit=3) for e in p]
    assert [e["text"] for e in anxious] == [f"запись {n}" for n in (9, 6, 3, 0)]

    both = [e for p in walk(client, "/api/entries", tag="работа", emotion="тревога") for e in p]
    assert [e["text"] for e in both] == ["запись 6", "запись 0"]

    ranged = [
        e
        for p in walk(client, "/api/entries", **{"from": "2026-08-03", "to": "2026-08-06"}, limit=3)
        for e in p
    ]
    assert [e["date"] for e in ranged] == [f"2026-08-0{d}" for d in (6, 5, 4, 3)]

    combined = walk(
        client, "/api/entries", tag="дом", **{"from": "2026-08-04", "to": "2026-08-10"}, limit=2
    )
    assert [e["text"] for p in combined for e in p] == [f"запись {n}" for n in (9, 7, 5, 3)]
    assert client.get("/api/entries", params={"tag": "нет-такого"}).json() == []


@pytest.mark.acceptance("kognis-3mh", "AC2")
def test_labels_list_for_filter_options(client: TestClient) -> None:
    signup(client, "ann@example.com")
    add_entry(client, "раз", "2026-08-01", tags=["работа", "дом"], emotions=["тревога"])
    add_entry(client, "два", "2026-08-02", tags=["дом"], emotions=["радость"])
    other = TestClient(client.app)
    signup(other, "bob@example.com")
    add_entry(other, "чужая", "2026-08-03", tags=["секрет"], emotions=["гнев"])
    assert client.get("/api/entries/labels").json() == {
        "tags": ["дом", "работа"],
        "emotions": ["радость", "тревога"],
    }
