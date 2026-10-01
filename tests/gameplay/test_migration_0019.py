"""Миграция 0019: искры — expand, откат удаляет только новые таблицы (kognis-crn, 2b)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from kognis.db import make_engine, transaction
from kognis.gameplay import QuestService, SparkRepository
from kognis.gameplay._app import GameplayService

ROOT = Path(__file__).resolve().parents[2]

# дни с дневником у пользователя прошлой версии
HISTORY = [-3, -2, -1, 0]


@pytest.mark.migration
def test_spark_tables_expand_and_downgrade_drops_only_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "0018")  # схема прошлого релиза
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

    command.upgrade(config, "0019")
    with transaction(engine) as session:  # новые таблицы работают, старые данные видны
        service = GameplayService(session)
        service.save_settings(1, [], 3, today)
        quest = QuestService(session).accept_template(1, "strengths", today)
        for idx in range(3):
            QuestService(session).complete_step(1, quest.id, idx, today)
        repo = SparkRepository(session)
        earned = repo.earned(1)
        assert earned >= 20  # недельная цель закрыта: искры начислены и после миграции

    command.downgrade(config, "0018")  # откат удаляет только добавленное
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        }
        seeded = conn.execute(
            text("SELECT COUNT(*) FROM xp_events WHERE ref LIKE '1-%'")
        ).scalar_one()
    assert "spark_events" not in tables
    assert "spark_purchases" not in tables
    assert seeded == len(HISTORY)  # данные прошлой версии не тронуты
