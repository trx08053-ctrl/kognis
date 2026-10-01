"""Цифровые герои в интерфейсе: приёмочные kognis-zjg AC3 и AC4 — компонентные тесты vitest."""

import pytest

from .test_motivation_frontend import run_vitest


@pytest.mark.source
@pytest.mark.acceptance("kognis-zjg", "AC3")
def test_mentor_line_only_for_unlocked_direction() -> None:
    run_vitest("src/heroes.test.tsx")


@pytest.mark.source
@pytest.mark.acceptance("kognis-zjg", "AC4")
def test_no_hero_lines_next_to_crisis_content() -> None:
    run_vitest("src/heroes.test.tsx")
