#!/usr/bin/env python3
"""Параллельная работа: изолированные рабочие копии (git worktree) и проверка их объединения.

    worktree.py new <task-id>          ../<repo>-<id>, ветка feat/<id>, uv sync, задача in_progress
    worktree.py list                   рабочие копии и их ветки
    worktree.py run <id>... [-- args]  параллельно agent_run.py, каждый агент в своей копии
    worktree.py integrate <branch>...  временная ветка integration/<время> от main: merge всех
                                       веток, перегенерация MAP при конфликте, verify результата
    worktree.py remove <task-id>       удалить рабочую копию (ветка остаётся)

Состояние задач (bd) общее для всех копий. Слияние в main — решение человека: integrate только
проверяет и печатает команду. Файл защищён.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = {"docs/MAP.md", ".beads/issues.jsonl", "CHANGELOG.md"}


def run(*cmd: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        sys.exit(f"{' '.join(cmd)}: {(proc.stderr or proc.stdout).strip()[-500:]}")
    return proc


def main_root() -> Path:
    common = run("git", "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    return Path(common).parent


def wt_path(task_id: str) -> Path:
    root = main_root()
    return root.parent / f"{root.name}-{task_id}"


def cmd_new(task_id: str) -> Path:
    path = wt_path(task_id)
    if path.exists():
        print(f"уже есть: {path}")
        return path
    run("git", "worktree", "add", "-q", str(path), "-b", f"feat/{task_id}", "main")
    run("uv", "sync", "--locked", "-q", cwd=path)
    run(sys.executable, "scripts/task.py", "start", task_id, cwd=path, check=False)
    print(f"{path}  (ветка feat/{task_id})")
    return path


def cmd_list() -> None:
    print(run("git", "worktree", "list").stdout.strip())


def cmd_run(ids: list[str], extra: list[str]) -> int:
    procs: dict[str, tuple[subprocess.Popen[str], Path]] = {}
    for task_id in ids:
        path = cmd_new(task_id)
        log = (path / ".agent-log").resolve()
        log.mkdir(exist_ok=True)
        out = (log / "parallel.out").open("w")
        procs[task_id] = (
            subprocess.Popen(
                [sys.executable, "scripts/agent_run.py", "--task", task_id, *extra],
                cwd=path,
                stdout=out,
                stderr=subprocess.STDOUT,
                text=True,
            ),
            path,
        )
        print(f"запущен агент: {task_id} в {path}")
    failed = 0
    for task_id, (proc, path) in procs.items():
        code = proc.wait()
        tail = (path / ".agent-log" / "parallel.out").read_text().strip().splitlines()[-1:]
        print(f"{task_id}: exit {code} · {tail[0] if tail else ''}")
        failed += code != 0
    return 1 if failed else 0


def resolve_generated(path: Path) -> bool:
    """Конфликты только в сгенерированных файлах разрешаются перегенерацией."""
    conflicted = set(run("git", "diff", "--name-only", "--diff-filter=U", cwd=path).stdout.split())
    if not conflicted or not conflicted <= GENERATED:
        return False
    for name in conflicted:
        run("git", "checkout", "--theirs", "--", name, cwd=path)
    if "docs/MAP.md" in conflicted:
        run(sys.executable, "scripts/gen_map.py", cwd=path)
    run("git", "add", *conflicted, cwd=path)
    run("git", "commit", "-q", "--no-edit", cwd=path)
    print(f"  конфликт в сгенерированных файлах разрешён перегенерацией: {sorted(conflicted)}")
    return True


def cmd_integrate(branches: list[str]) -> int:
    name = f"integration/{time.strftime('%Y%m%d-%H%M%S')}"
    path = main_root().parent / f"{main_root().name}-{name.replace('/', '-')}"
    run("git", "worktree", "add", "-q", str(path), "-b", name, "main")
    run("uv", "sync", "--locked", "-q", cwd=path)
    for branch in branches:
        merge = run("git", "merge", "--no-ff", "-q", "-m", f"chore: integrate {branch}", branch,
                    cwd=path, check=False)  # fmt: skip
        if merge.returncode != 0 and not resolve_generated(path):
            conflicted = run(
                "git", "diff", "--name-only", "--diff-filter=U", cwd=path
            ).stdout.split()
            run("git", "merge", "--abort", cwd=path, check=False)
            print(f"FAIL: конфликт при слиянии {branch} в файлах {conflicted} — нужен ребейз ветки "
                  f"или решение человека. Копия: {path}")  # fmt: skip
            return 1
        print(f"  слита {branch}")
    if (path / "docs" / "MAP.md").exists():
        run(sys.executable, "scripts/gen_map.py", cwd=path)
        if run("git", "status", "--porcelain", cwd=path).stdout.strip():
            run("git", "commit", "-qam", "docs: regenerate map after integration", cwd=path)
    verify = subprocess.run([sys.executable, "scripts/verify.py"], cwd=path, check=False)
    if verify.returncode != 0:
        print(f"FAIL: объединённый результат не проходит verify. Копия: {path}")
        return 1
    print(
        f"\nOK: {', '.join(branches)} вместе проходят verify ({name}).\n"
        f"Слияние в main (решение человека): git switch main && git merge --ff-only {name}\n"
        f"Убрать копию: git worktree remove {path}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new").add_argument("id")
    sub.add_parser("list")
    run_p = sub.add_parser("run")
    run_p.add_argument("ids", nargs="+")
    sub.add_parser("integrate").add_argument("branches", nargs="+")
    sub.add_parser("remove").add_argument("id")
    argv = sys.argv[1:]
    extra: list[str] = []
    if "--" in argv:
        extra = argv[argv.index("--") + 1 :]
        argv = argv[: argv.index("--")]
    args = parser.parse_args(argv)
    if args.cmd == "new":
        cmd_new(args.id)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "run":
        return cmd_run(args.ids, extra)
    elif args.cmd == "integrate":
        return cmd_integrate(args.branches)
    elif args.cmd == "remove":
        run("git", "worktree", "remove", str(wt_path(args.id)))
        print(f"удалена копия {wt_path(args.id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
