"""Преемственность разборов в интерфейсе: приёмочный kognis-sky AC6 — компонентные тесты vitest."""

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
@pytest.mark.acceptance("kognis-sky", "AC6")
def test_changes_block_memory_panel_and_default_period_in_ui() -> None:
    run_vitest("src/analysisContinuity.test.tsx")
