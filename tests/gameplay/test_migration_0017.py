"""Миграция 0017: ранее полученные достижения сохраняются (kognis-0a8, AC3)."""

from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from kognis.db import make_engine, transaction
from kognis.gameplay import GameplayService

ROOT = Path(__file__).resolve().parents[2]

# пользователь → (код, дата получения) на схеме 0016
OLD = {
    1: [("first_entry", "2026-09-01"), ("streak_3", "2026-09-03"), ("streak_7", "2026-09-07")],
    2: [("streak_30", "2026-09-20"), ("reviews_10", "2026-09-10")],
    3: [("streak_3", "2026-09-03"), ("consistency_1", "2026-09-08")],  # новое уже есть — без дубля
}


def _rows(url: str) -> list[tuple[int, str, str]]:
    engine = make_engine(url)
    with engine.connect() as conn:
        found = conn.execute(
            text("SELECT owner_id, code, earned_on FROM achievements ORDER BY owner_id, code")
        ).all()
    return [(r.owner_id, r.code, str(r.earned_on)) for r in found]


@pytest.mark.migration
@pytest.mark.acceptance("kognis-0a8", "AC3")
def test_earned_achievements_survive_and_map_to_new_levels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "0016")  # схема прошлого релиза
    engine = make_engine(url)
    with engine.begin() as conn:
        for owner, earned in OLD.items():
            for code, day in earned:
                conn.execute(
                    text(
                        "INSERT INTO achievements (owner_id, code, earned_on, created_at) "
                        "VALUES (:o, :c, :d, '2026-09-30 00:00:00')"
                    ),
                    {"o": owner, "c": code, "d": day},
                )

    command.upgrade(config, "0017")
    after = set(_rows(url))
    for owner, earned in OLD.items():  # ничего не потеряно, даты прежние
        assert {(owner, code, day) for code, day in earned} <= after
    assert (1, "consistency_1", "2026-09-07") in after  # серия 7 → бронза «Постоянства»
    assert (2, "consistency_1", "2026-09-20") in after
    assert (2, "consistency_2", "2026-09-20") in after  # серия 30 → и серебро
    assert len([r for r in after if r[0] == 3 and r[1] == "consistency_1"]) == 1
    assert not any(
        code in {"consistency_2", "consistency_3"} for o, code, _ in after if o in (1, 3)
    )

    with transaction(engine) as session:  # и интерфейс их видит
        progress = GameplayService(session).progress(2, date(2026, 9, 30))
    earned_codes = {a.code for a in progress.achievements}
    assert {"streak_30", "reviews_10", "consistency_1", "consistency_2"} <= earned_codes

    command.downgrade(config, "0016")  # добавленное миграцией уходит, старое остаётся
    back = set(_rows(url))
    assert back == {(o, c, d) for o, earned in OLD.items() for c, d in earned} - {
        (3, "consistency_1", "2026-09-08")
    }
