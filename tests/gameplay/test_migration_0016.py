"""Миграция 0016: серии существующих пользователей не уменьшаются (kognis-3r1, AC4)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from kognis.db import make_engine, transaction
from kognis.gameplay import GameplayService
from kognis.gameplay._domain import streak_length

ROOT = Path(__file__).resolve().parents[2]

# смещения дней от «сегодня» у трёх пользователей прошлой версии: серия с заморозкой, серия с
# «висящей» заморозкой (последняя активность позавчера), серия оборвана давно
HISTORIES = {
    1: [-12, -11, -10, -8, -7, -6, -5, -4, -3, -2, -1, 0],
    2: [-9, -8, -7, -6, -5, -2],
    3: [-40, -39, -38, -20, -19],
}


@pytest.mark.migration
@pytest.mark.acceptance("kognis-3r1", "AC4")
def test_existing_streaks_do_not_shrink_after_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "0015")  # схема прошлого релиза
    today = datetime.now(UTC).date()
    engine = make_engine(url)
    with engine.begin() as conn:
        for owner, offsets in HISTORIES.items():
            for n, offset in enumerate(offsets):
                conn.execute(
                    text(
                        "INSERT INTO xp_events (owner_id, kind, ref, day, xp, created_at) "
                        "VALUES (:o, 'entry', :r, :d, 10, '2026-01-01 00:00:00')"
                    ),
                    {"o": owner, "r": f"{owner}-{n}", "d": today + timedelta(days=offset)},
                )
    old = {
        owner: streak_length([today + timedelta(days=n) for n in offsets], today)
        for owner, offsets in HISTORIES.items()
    }
    # сценарий действительно содержит все случаи: живые серии и давний обрыв
    assert min(old[1], old[2]) > 0
    assert old[3] == 0

    command.upgrade(config, "head")  # схема новее 0016; правила серии те же
    with transaction(engine) as session:
        service = GameplayService(session)
        after = {owner: service.progress(owner, today) for owner in HISTORIES}
    for owner, streak in old.items():
        assert after[owner].streak >= streak, owner  # не меньше прежней
        assert after[owner].weekly_goal == 3
    # заморозки прошлой версии бесплатны; запас стартует полным, висящая заморозка тратит одну
    assert (after[1].freezes, after[2].freezes) == (2, 1)
    assert after[3].recovery is None  # давний обрыв вне окна восстановления

    with engine.connect() as conn:
        rules_from = conn.execute(
            text("SELECT rules_from FROM gameplay_settings WHERE owner_id = 1")
        ).scalar_one()
    assert date.fromisoformat(str(rules_from)) == today

    command.downgrade(config, "0015")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM xp_events")).scalar_one() == sum(
            map(len, HISTORIES.values())
        )
