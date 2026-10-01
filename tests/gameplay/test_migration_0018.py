"""Миграция 0018: expand, откат удаляет только новые таблицы (kognis-zjg, 2b)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from kognis.db import make_engine, transaction
from kognis.gameplay import HeroService

ROOT = Path(__file__).resolve().parents[2]

# дни с дневником у двух пользователей прошлой версии
HISTORY = {1: [-3, -2, -1, 0], 2: [-40, -39]}


@pytest.mark.migration
def test_companion_tables_expand_and_downgrade_drops_only_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "0017")  # схема прошлого релиза
    today = datetime.now(UTC).date()
    engine = make_engine(url)
    with engine.begin() as conn:
        for owner, offsets in HISTORY.items():
            for n, offset in enumerate(offsets):
                conn.execute(
                    text(
                        "INSERT INTO xp_events (owner_id, kind, ref, day, xp, created_at) "
                        "VALUES (:o, 'entry', :r, :d, 10, '2026-01-01 00:00:00')"
                    ),
                    {"o": owner, "r": f"{owner}-{n}", "d": today + timedelta(days=offset)},
                )

    command.upgrade(config, "0018")
    with transaction(engine) as session:  # новые таблицы работают, старые данные видны
        state = HeroService(session).choose(1, "fox", "Луна", "ty", today)
    assert state.chosen
    assert state.days_total == 4  # дни с дневником считаются и после миграции

    command.downgrade(config, "0017")  # откат удаляет только добавленное
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        }
        events = conn.execute(text("SELECT COUNT(*) FROM xp_events")).scalar_one()
    assert "companions" not in tables
    assert "companion_postcards" not in tables
    assert events == sum(len(days) for days in HISTORY.values())  # старое не тронуто
