#!/usr/bin/env python3
"""Жизненный цикл задачи: Beads (граф и статус) + tasks/<id>/ (TASK.md, PROGRESS.md).

    task.py new "Название" [--type feature] [--priority 2] [--deps id1,id2]
    task.py start <id>                 статус in_progress
    task.py block <id> "причина" [--kind needs_input|budget|infra|no_progress]
                                       статус blocked + причина в bd и PROGRESS.md
    task.py done <id>                  закрыть: заново прогоняет verify (файлу evidence не доверяет)
                                       и требует приёмочный тест на каждый критерий AC из TASK.md
    task.py list                       задачи в работе / заблокированные и их следующий шаг

Статус задачи хранится только в bd; PROGRESS.md — передача контекста следующей сессии.

Файл защищён: изменять только с одобрения человека.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"
TEMPLATES = ROOT / "docs" / "templates"


def bd(*args: str) -> str:
    proc = subprocess.run(["bd", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.exit(f"bd {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def bd_json(*args: str) -> Any:
    return json.loads(bd(*args, "--json"))


def bd_items(*args: str) -> list[dict[str, Any]]:
    """bd --json всегда нормализуется в список объектов."""
    data = bd_json(*args)
    raw = cast("list[Any]", data if isinstance(data, list) else [data])
    return [x for x in raw if isinstance(x, dict)]


def progress_path(task_id: str) -> Path:
    return TASKS / task_id / "PROGRESS.md"


def add_blocker_note(task_id: str, note: str) -> None:
    path = progress_path(task_id)
    if path.exists():
        text = path.read_text().replace(
            "## Блокеры и вопросы человеку\n", f"## Блокеры и вопросы человеку\n- {note}\n", 1
        )
        path.write_text(text)


AC_ROW = re.compile(r"^\|\s*(AC\d+)\s*\|(.*)$", re.M)
META_AC = re.compile(r"verify|evidence|task-done|задача закрыта|ревью|review", re.I)


def uncovered_acceptance(task_id: str) -> list[str]:
    """AC из TASK.md без теста @pytest.mark.acceptance("<id>", "ACn"); мета-AC не нужны."""
    task_md = TASKS / task_id / "TASK.md"
    if not task_md.exists():
        return []
    required = [ac for ac, rest in AC_ROW.findall(task_md.read_text()) if not META_AC.search(rest)]
    marked: set[str] = set()
    pattern = re.compile(rf"acceptance\(\s*[\"']{re.escape(task_id)}[\"']\s*,\s*[\"'](AC\d+)[\"']")
    for test in (ROOT / "tests").rglob("*.py"):
        marked.update(pattern.findall(test.read_text()))
    return [ac for ac in dict.fromkeys(required) if ac not in marked]


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def cmd_new(args: argparse.Namespace) -> None:
    created = bd_items("create", args.title, "-t", args.type, "-p", str(args.priority))
    task_id = str(created[0].get("id", "")) if created else ""
    if not task_id:
        sys.exit("bd create не вернул id")
    for dep in filter(None, (args.deps or "").split(",")):
        bd("dep", "add", task_id, dep.strip())
    folder = TASKS / task_id
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("TASK.md", "PROGRESS.md"):
        text = (TEMPLATES / name).read_text()
        text = text.replace("bd-XXX", task_id).replace("<короткое название>", args.title)
        text = text.replace("YYYY-MM-DD", today())
        (folder / name).write_text(text)
    print(f"{task_id}\nсоздано: {folder.relative_to(ROOT)}/TASK.md, PROGRESS.md")


def cmd_start(args: argparse.Namespace) -> None:
    items = bd_items("show", args.id)
    status = str(items[0].get("status")) if items else ""
    if status == "blocked":  # человек ответил на блокер — возвращаем в работу
        bd("update", args.id, "--status", "in_progress")
        print(f"{args.id}: blocked → in_progress")
        return
    bd("update", args.id, "--claim")  # атомарный захват: второй агент получит отказ
    print(f"{args.id}: in_progress (захвачена)")


def cmd_block(args: argparse.Namespace) -> None:
    note = f"BLOCKED[{args.kind}]: {args.reason}"
    bd("update", args.id, "--status", "blocked", "--append-notes", note)
    add_blocker_note(args.id, f"{today()} [{args.kind}] {args.reason}")
    metrics.record_task(args.id, f"blocked:{args.kind}", note=args.reason)
    print(f"{args.id}: blocked [{args.kind}] — {args.reason}")


def cmd_done(args: argparse.Namespace) -> None:
    ui = TASKS / args.id / "ui-feedback.md"
    open_ui = re.findall(r"^## (UI-\d+) · open ·", ui.read_text(), re.M) if ui.exists() else []
    if open_ui:
        sys.exit(f"Нельзя закрыть: открытые UI-замечания {open_ui} в {ui.relative_to(ROOT)}.")
    missing = uncovered_acceptance(args.id)
    if missing:
        sys.exit(
            f"Нельзя закрыть: критерии {missing} из TASK.md без приёмочного теста "
            f'(@pytest.mark.acceptance("{args.id}", "ACn") — сценарий через публичный интерфейс).'
        )
    # файлу .evidence не доверяем (агент может его записать) — проверяем заново
    proc = subprocess.run([sys.executable, "scripts/verify.py"], cwd=ROOT, check=False)
    if proc.returncode != 0:
        sys.exit("Нельзя закрыть задачу: verify не прошёл.")
    evidence = json.loads((ROOT / ".evidence" / "latest.json").read_text())
    proof = f"verify tree {str(evidence['tree'])[:12]} head {str(evidence['head'])[:12]}"
    bd("close", args.id, "--reason", proof)
    metrics.record_task(args.id, "accepted", args.human_min)
    print(f"{args.id}: closed ({proof})")
    commit_state(args.id)


def git_out(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
    )
    return proc.stdout


def commit_state(task_id: str) -> None:
    """Экспорт bd после закрытия — отдельным коммитом: следующий шаг начинается с чистого дерева."""
    export = ".beads/issues.jsonl"
    if git_out("status", "--porcelain", "--", export).strip():
        git_out("commit", "-q", "-m", f"chore(bd): close {task_id}", "--", export)
    rest = [ln[3:] for ln in git_out("status", "--porcelain", "--untracked-files=no").splitlines()]
    if rest:
        print(f"ВНИМАНИЕ: незакоммиченные изменения после закрытия: {rest} — закоммить их.")


def cmd_list(_: argparse.Namespace) -> None:
    for status in ("in_progress", "blocked"):
        for item in bd_items("list", "--status", status):
            task_id = str(item["id"])
            path = progress_path(task_id)
            step = "(нет PROGRESS.md)"
            if path.exists():
                match = re.search(
                    r"^## Следующий шаг\s*\n(.+?)(?=^## |\Z)", path.read_text(), re.M | re.S
                )
                step = match.group(1).strip()[:300] if match else "(не записан)"
            print(f"{task_id} [{status}] · {item['title']}\n  следующий шаг: {step}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    new = sub.add_parser("new")
    new.add_argument("title")
    new.add_argument("--type", default="task", choices=["task", "feature", "bug", "chore", "epic"])
    new.add_argument("--priority", type=int, default=2)
    new.add_argument("--deps", help="id задач, от которых зависит новая, через запятую")
    new.set_defaults(func=cmd_new)
    start = sub.add_parser("start")
    start.add_argument("id")
    start.set_defaults(func=cmd_start)
    done = sub.add_parser("done")
    done.add_argument("id")
    done.add_argument("--human-min", type=float, help="минуты участия человека (вводит человек)")
    done.set_defaults(func=cmd_done)
    block = sub.add_parser("block")
    block.add_argument("id")
    block.add_argument("reason")
    block.add_argument(
        "--kind", default="needs_input", choices=["needs_input", "budget", "infra", "no_progress"]
    )
    block.set_defaults(func=cmd_block)
    sub.add_parser("list").set_defaults(func=cmd_list)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
