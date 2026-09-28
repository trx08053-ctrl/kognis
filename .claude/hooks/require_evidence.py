#!/usr/bin/env python3
"""Stop: не даёт завершить ход с непроверенным кодом или устаревшим PROGRESS.md.

1. В рабочей копии есть изменения кода, а для текущего tree-hash нет успешного evidence →
   запустить `just verify` или явно сообщить пользователю, что изменения не проверены.
2. У задачи в работе (статус in_progress в bd) после последнего
   обновления PROGRESS.md появились коммиты → записать сделанное и следующий шаг.
Блокирует один раз за ход (stop_hook_active), чтобы не зациклиться.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

SHOW_MAX = 8
NON_CODE_PREFIXES = ("docs/", "tasks/", ".beads/", "CHANGELOG.md", "README.md", "AGENTS.md")


def run(root: Path, *cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)


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


def real(path: Path) -> bool:
    """Не заглушка песочницы (/dev/null на месте несуществующего служебного пути)."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        return True  # удалённый файл — реальное изменение
    return stat.S_ISREG(mode) or stat.S_ISLNK(mode) or stat.S_ISDIR(mode)


def unverified_code(root: Path) -> str | None:
    changed = [line[3:] for line in run(root, "git", "status", "--porcelain").stdout.splitlines()]
    code = [p for p in changed if not p.startswith(NON_CODE_PREFIXES) and real(root / p)]
    if not code or run(root, sys.executable, "scripts/verify.py", "--status").returncode == 0:
        return None
    shown = ", ".join(code[:SHOW_MAX]) + (" …" if len(code) > SHOW_MAX else "")
    return (
        f"Есть непроверенные изменения кода ({shown}). "
        "Запусти `just verify` и приведи результат (tree/evidence). "
        "Если остановка намеренная (вопрос человеку, блокер, исследование) — "
        "прямо напиши пользователю, что изменения НЕ проверены и почему."
    )


def stale_progress(root: Path) -> str | None:
    head_time = run(root, "git", "log", "-1", "--format=%ct").stdout.strip()
    if not head_time:
        return None
    stale: list[str] = []
    for task_id in bd_ids(root, "in_progress"):
        progress = root / "tasks" / task_id / "PROGRESS.md"
        if not progress.exists():
            continue
        rel = str(progress.relative_to(root))
        if run(root, "git", "status", "--porcelain", "--", rel).stdout.strip():
            continue  # уже обновлён, но не закоммичен — это нормально
        touched = run(root, "git", "log", "-1", "--format=%ct", "--", rel).stdout.strip()
        if not touched or int(touched) < int(head_time):
            stale.append(rel)
    if not stale:
        return None
    return (
        f"После последнего обновления {', '.join(stale)} были коммиты. "
        "Запиши в PROGRESS.md: что сделано (коммит, evidence) и конкретный «Следующий шаг», "
        "затем закоммить — иначе следующая сессия не продолжит с нужного места."
    )


def main() -> None:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", ".")))
    reasons = [r for r in (unverified_code(root), stale_progress(root)) if r]
    if reasons:
        print(json.dumps({"decision": "block", "reason": " ".join(reasons)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
