"""GameplayService: устойчивость к параллельной выдаче достижения."""

from datetime import date

import pytest
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.gameplay import GameplayService, _infra
from kognis.gameplay._app import RecoveryUnavailableError

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


def _broken_streak(engine: Engine) -> date:
    """Серия из трёх дней, затем три пропуска (запас заморозок — две): «сегодня» — 13 сентября."""
    with transaction(engine) as session:
        for n in range(3):
            day = date(2026, 9, 7 + n)
            GameplayService(session).award_entry(1, 200 + n, day, day)
    return date(2026, 9, 13)


def test_repository_refuses_a_second_recovery_for_the_same_break(engine: Engine) -> None:
    with transaction(engine) as session:
        repo = _infra.ProgressRepository(session)
        assert repo.add_recovery(1, date(2026, 9, 9), date(2026, 9, 12), "раз")
        assert not repo.add_recovery(1, date(2026, 9, 9), date(2026, 9, 12), "два")


def test_concurrent_recovery_is_reported_as_unavailable(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Параллельный запрос успел записать восстановление первым: второй получает отказ, не 500."""
    today = _broken_streak(engine)

    def already_taken(*_args: object) -> bool:
        return False

    monkeypatch.setattr(_infra.ProgressRepository, "add_recovery", already_taken)
    with transaction(engine) as session, pytest.raises(RecoveryUnavailableError):
        GameplayService(session).recover(1, "Заболел", today)
