#!/usr/bin/env python3
"""Метрики доработок: общие функции для agent_run, task.py и costs.py.

Хранятся только метаданные (без содержимого файлов, промптов и секретов):
- .agent-log/runs.jsonl  — сессии agent_run (время, ходы, оценка стоимости, чтения, прогоны verify);
- .agent-log/tasks.jsonl — исходы задач (принята / заблокирована, модули, файлы, время человека).
Стоимость — оценка Claude Code по прайсу Claude; для моделей по подписке это не счёт. Файл защищён.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / ".agent-log"
TASKS_LOG = LOG / "tasks.jsonl"
MODULE_PART = 2  # src/<pkg>/<модуль>/…


def harness_version() -> str:
    answers = ROOT / ".copier-answers.yml"
    match = re.search(r"^_commit:\s*(\S+)", answers.read_text(), re.M) if answers.exists() else None
    return match.group(1) if match else "unknown"


def project_slug() -> str:
    settings = ROOT / ".claude" / "settings.json"
    match = re.search(r"project=([\w.-]+)", settings.read_text()) if settings.exists() else None
    return match.group(1) if match else ROOT.name


def task_meta(task_id: str) -> dict[str, str]:
    """Тип (bd) и риск (строка «Тип:» в TASK.md: trivial / standard / risky)."""
    out = subprocess.run(
        ["bd", "show", task_id, "--json"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout
    try:
        data = json.loads(out or "{}")
    except ValueError:
        data = {}
    raw = cast("list[Any]", data if isinstance(data, list) else [data])
    item = cast("dict[str, Any]", raw[0]) if raw and isinstance(raw[0], dict) else {}
    task_md = ROOT / "tasks" / task_id / "TASK.md"
    text = task_md.read_text() if task_md.exists() else ""
    risk = re.search(r"\*\*Тип:\*\*\s*(trivial|standard|risky)", text)
    return {
        "type": str(item.get("issue_type", "task")),
        "risk": risk.group(1) if risk else "unknown",
        "title": str(item.get("title", "")),
    }


def session_stats(session_id: str) -> dict[str, int]:
    """Чтения файлов, прогоны verify и их падения по журналу инструментов одной сессии."""
    prefix = session_id[:8]
    stats = {"reads": 0, "verify_runs": 0, "verify_fails": 0, "tool_errors": 0}
    for path in sorted(LOG.glob("20*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r.get("session") != prefix:
                continue
            stats["reads"] += r.get("tool") == "Read"
            stats["tool_errors"] += not r.get("ok", True)
            if r.get("tool") == "Bash" and re.search(r"verify", str(r.get("target", ""))):
                stats["verify_runs"] += 1
                stats["verify_fails"] += not r.get("ok", True)
    return stats


def changed_files(task_id: str) -> list[str]:
    out = subprocess.run(
        ["git", "log", f"--grep={task_id}", "--name-only", "--format="],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout  # fmt: skip
    return sorted({f for f in out.splitlines() if f and not f.startswith((".beads/", "tasks/"))})


def modules_of(files: list[str]) -> list[str]:
    src = ROOT / "src"
    packages = [p for p in src.iterdir() if (p / "__init__.py").exists()] if src.exists() else []
    if len(packages) != 1:
        return []
    pkg = packages[0].name
    return sorted(
        {
            f.split("/")[MODULE_PART]
            for f in files
            if f.startswith(f"src/{pkg}/") and f.count("/") > MODULE_PART
        }
    )


def record_task(task_id: str, outcome: str, human_min: float | None = None, note: str = "") -> None:
    files = changed_files(task_id)
    rec: dict[str, object] = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "task": task_id,
        **task_meta(task_id),
        "outcome": outcome,
        "harness": harness_version(),
        "files_changed": len(files),
        "modules": modules_of(files),
        "human_min": human_min,
        "note": note[:200],
    }
    LOG.mkdir(exist_ok=True)
    with TASKS_LOG.open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
