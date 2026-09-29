#!/usr/bin/env python3
"""Перенос ветки в main только после зелёного CI на этой ветке. Файл защищён. Решение человека.

    land.py [ветка]     по умолчанию — текущая (не main)

1. рабочее дерево чистое, ветка — прямое продолжение origin/main (иначе `just sync-main`);
2. push ветки → ждём CI для её коммита;
3. CI зелёный → fast-forward origin/main на этот коммит; красный → main не трогается.
Заменяет защиту ветки на GitHub (недоступна для приватных репозиториев на бесплатном тарифе):
в main попадает только то, что уже прошло CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

POLL_S = 15
WAIT_S = 45 * 60


def run(*cmd: str, check: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        sys.exit(f"ошибка: {' '.join(cmd[:3])}…\n{(proc.stdout + proc.stderr).strip()[-800:]}")
    return proc.stdout.strip()


def ci_status(sha: str) -> tuple[str, str]:
    """(status, conclusion) последнего прогона CI для коммита; ("", "") — прогона ещё нет."""
    out = run(
        "gh", "run", "list", "--commit", sha, "--limit", "5", "--json", "status,conclusion,url"
    )
    runs = json.loads(out or "[]")
    if not runs:
        return "", ""
    return str(runs[0]["status"]), str(runs[0].get("conclusion") or "")


def main() -> int:
    branch = sys.argv[1] if len(sys.argv) > 1 else run("git", "rev-parse", "--abbrev-ref", "HEAD")
    if branch in {"main", "HEAD"}:
        sys.exit(
            "работа — в ветке задачи (git switch -c task/<id>); main обновляется только через land"
        )
    if run("git", "status", "--porcelain", "--untracked-files=no"):
        sys.exit("есть незакоммиченные изменения — закоммитьте")
    run("git", "fetch", "-q", "origin", "main")
    sha = run("git", "rev-parse", branch)
    ancestor = ["git", "merge-base", "--is-ancestor", "origin/main", sha]
    if subprocess.run(ancestor, check=False).returncode != 0:
        sys.exit(f"{branch} не продолжает origin/main — `just sync-main`, затем снова land")
    run("git", "push", "-q", "origin", f"{branch}:{branch}")
    print(f"── CI для {branch} @ {sha[:7]}…", flush=True)
    deadline = time.monotonic() + WAIT_S
    status, conclusion = "", ""
    while time.monotonic() < deadline:
        status, conclusion = ci_status(sha)
        if status == "completed":
            break
        time.sleep(POLL_S)
    if conclusion != "success":
        sys.exit(
            f"CI: {conclusion or status or 'не запущен'} — main не изменён (детали: `gh run view`)"
        )
    run("git", "push", "-q", "origin", f"{sha}:refs/heads/main")
    print(f"OK: main = {sha[:7]} ({branch}, CI зелёный)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
