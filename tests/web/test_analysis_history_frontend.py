"""История разборов в интерфейсе: приёмочные kognis-qkh (AC2, AC3) — компонентные тесты vitest."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_vitest(name: str) -> None:
    pnpm = shutil.which("pnpm")
    assert pnpm, "нет pnpm"
    result = subprocess.run(
        [pnpm, "--dir", "frontend", "exec", "vitest", "run", "--coverage.enabled=false", name],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.source
@pytest.mark.acceptance("kognis-qkh", "AC2")
def test_history_list_is_paged_newest_first_in_ui() -> None:
    run_vitest("src/analysisHistory.test.tsx")


@pytest.mark.source
@pytest.mark.acceptance("kognis-qkh", "AC3")
def test_opening_past_analysis_shows_patterns_quotes_questions_answers_in_ui() -> None:
    run_vitest("src/analysisHistory.test.tsx")
