#!/usr/bin/env python3
"""SessionStart: краткая сводка состояния, чтобы продолжить работу после прерывания."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def sh(*cmd: str, limit: int = 15) -> str:
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "(недоступно)"
    lines = (out.stdout or out.stderr).strip().splitlines()
    tail = [f"… ещё {len(lines) - limit}"] if len(lines) > limit else []
    return "\n".join(lines[:limit] + tail) or "(пусто)"


def bd_ids(root: Path, status: str) -> list[str]:
    """id задач с данным статусом из bd (единственный источник статуса)."""
    try:
        out = subprocess.run(
            ["bd", "list", "--status", status, "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout
        items = json.loads(out or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    return [str(i["id"]) for i in items if isinstance(i, dict) and "id" in i]


def next_steps() -> list[str]:
    result: list[str] = []
    for status in ("in_progress", "blocked"):
        for task_id in bd_ids(ROOT, status):
            progress = ROOT / "tasks" / task_id / "PROGRESS.md"
            text = progress.read_text() if progress.exists() else ""
            match = re.search(r"^## Следующий шаг\s*\n(.+?)(?=^## |\Z)", text, re.M | re.S)
            step = match.group(1).strip() if match else "(не записан — запиши!)"
            result.append(f"- {task_id} [{status}]: {step[:400]}")
    return result


def main() -> None:
    parts = [
        "## Состояние проекта (SessionStart)",
        f"Ветка: {sh('git', 'branch', '--show-current')} · "
        f"последний коммит: {sh('git', 'log', '-1', '--format=%h %s (%cr)')}",
        "Изменения в рабочей копии:\n" + sh("git", "status", "--short"),
        "Evidence: " + sh("python3", "scripts/verify.py", "--status"),
    ]
    if shutil.which("bd") and (ROOT / ".beads").exists():
        parts.append("В работе (bd):\n" + sh("bd", "list", "--status", "in_progress"))
        parts.append("Готовы к работе (bd ready):\n" + sh("bd", "ready", limit=10))
    steps = next_steps()
    if steps:
        parts.append("Следующие шаги из tasks/*/PROGRESS.md:\n" + "\n".join(steps))
    parts.append("Порядок работы и ограничения: AGENTS.md.")
    print("\n\n".join(parts))


if __name__ == "__main__":
    main()
