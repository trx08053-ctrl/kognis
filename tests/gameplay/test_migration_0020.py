"""Миграция 0020: квест дня — expand, откат удаляет только новую таблицу (kognis-crn, 2b)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from kognis.db import make_engine, transaction
from kognis.gameplay import DailyDoneTodayError, QuestService

ROOT = Path(__file__).resolve().parents[2]

HISTORY = [-2, -1, 0]  # дни с дневником пользователя прошлой версии


@pytest.mark.migration
def test_daily_picks_expand_and_downgrade_drops_only_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "0019")  # схема прошлого релиза
    today = datetime.now(UTC).date()
    engine = make_engine(url)
    with engine.begin() as conn:
        for n, offset in enumerate(HISTORY):
            conn.execute(
                text(
                    "INSERT INTO xp_events (owner_id, kind, ref, day, xp, created_at) "
                    "VALUES (:o, 'entry', :r, :d, 10, '2026-01-01 00:00:00')"
                ),
                {"o": 1, "r": f"1-{n}", "d": today + timedelta(days=offset)},
            )

    command.upgrade(config, "0020")
    with transaction(engine) as session:  # новые таблицы работают, старые данные видны
        service = QuestService(session)
        state = service.daily(1, today)
        assert len(state.options) == 3
        assert state.picked is None
        chosen = service.choose_daily(1, state.options[0], today)
        done = service.complete_daily(1, today)
        assert chosen.picked == done.picked == state.options[0]
        assert done.done is True
        with pytest.raises(DailyDoneTodayError):  # выбор в этот день уже сделан
            service.choose_daily(1, state.options[1], today)

    command.downgrade(config, "0019")  # откат удаляет только добавленное
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        }
        seeded = conn.execute(
            text("SELECT COUNT(*) FROM xp_events WHERE ref LIKE '1-%'")
        ).scalar_one()
    assert "daily_picks" not in tables
    assert seeded == len(HISTORY)  # данные прошлой версии не тронуты
