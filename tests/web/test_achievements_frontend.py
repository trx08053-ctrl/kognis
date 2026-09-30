"""Экран достижений и отметки рефлексии: приёмочный kognis-0a8 AC2 — компонентные тесты vitest."""

import pytest

from .test_motivation_frontend import run_vitest


@pytest.mark.source
@pytest.mark.acceptance("kognis-0a8", "AC2")
def test_achievement_grid_progress_hidden_and_marks_in_the_interface() -> None:
    run_vitest("src/achievements.test.tsx")
