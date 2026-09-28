"""GameplayService: устойчивость к параллельной выдаче достижения."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import GameplayService, _infra

TODAY = date(2026, 9, 1)


def test_concurrent_achievement_grant_does_not_fail_or_duplicate(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Второй запрос до коммита первого не видит достижения и пытается выдать его снова:
    запись при этом не теряется, достижение остаётся одно. Гонку имитирует «устаревшее» чтение."""
    with transaction(engine) as session:
        GameplayService(session).award_entry(1, 100, TODAY, TODAY)

    def stale_read(_repo: object, _owner_id: int) -> list[tuple[str, date]]:
        return []

    monkeypatch.setattr(_infra.ProgressRepository, "achievements", stale_read)
    with transaction(engine) as session:
        state = GameplayService(session).award_entry(1, 101, TODAY, TODAY)
    assert state.xp == 20
    monkeypatch.undo()

    with transaction(engine) as session:
        codes = [a.code for a in GameplayService(session).progress(1, TODAY).achievements]
    assert codes == ["first_entry"]
