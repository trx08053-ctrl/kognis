"""Мотивация 2.0 в интерфейсе: приёмочный kognis-3r1 AC3 — компонентные тесты vitest."""

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
@pytest.mark.acceptance("kognis-3r1", "AC3")
def test_broken_streak_shows_days_and_recovery_instead_of_zero() -> None:
    run_vitest("src/motivation.test.tsx")
