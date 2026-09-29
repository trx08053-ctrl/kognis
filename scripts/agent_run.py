#!/usr/bin/env python3
"""Автономный прогон агента по задаче с лимитами времени, денег и повторов.

    agent_run.py [--task ID] [--backend anthropic|ollama] [--model M] [--session-budget 2]
                 [--total-budget 6] [--session-timeout 1800] [--max-sessions 5] [--max-idle 2]

--backend ollama: Claude Code работает на модели Ollama Cloud (по умолчанию deepseek-v4.1-flash)
через Anthropic-совместимый API; ключ — OLLAMA_API_KEY из ~/.config/dev-harness/ollama.env.
Код уходит во внешнее облако. Стоимость в долларах Claude Code для чужой модели не считает —
лимитами служат таймаут, число сессий и остановка без прогресса.

Каждая сессия — новый `claude -p` (чистый контекст): состояние берётся из git, bd и
tasks/<id>/PROGRESS.md, поэтому прерывание (таймаут, сбой, Ctrl+C) не теряет работу.
Остановка: задача закрыта / blocked / исчерпан общий бюджет / max-idle сессий подряд без
прогресса (нет новых коммитов и изменений PROGRESS.md) / max-sessions.
Журнал сессий: .agent-log/runs.jsonl. Файл защищён.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / ".agent-log" / "runs.jsonl"
OLLAMA_ENV = Path(
    os.environ.get("DEV_HARNESS_OLLAMA_ENV", "~/.config/dev-harness/ollama.env")
).expanduser()
OLLAMA_MODEL = "deepseek-v4.1-flash"

PROMPT = """Ты работаешь автономно, человека рядом нет. Задача {id}: «{title}».
Следуй AGENTS.md. Контекст задачи: tasks/{id}/TASK.md и tasks/{id}/PROGRESS.md
(начни с раздела «Следующий шаг»; проверь git status/git log — прошлая сессия могла прерваться
посреди шага, незакоммиченные изменения — её незаконченная работа).
Выполняй шаги плана по одному: после каждого — `just verify`, коммит, обнови PROGRESS.md
(сделано / следующий шаг) и закоммить его.
Каждый критерий ACn из TASK.md подтверди приёмочным тестом через публичный интерфейс
с маркером @pytest.mark.acceptance("{id}", "ACn") (см. docs/TESTING.md).
Когда критерии выполнены, verify зелёный и ревью (subagent reviewer) без blocker —
выполни `python3 scripts/task.py done {id}` (он сам перезапустит verify).
Если нужен человек (действие из списка «только человек», ESCALATE после 3 попыток,
противоречие в требованиях) — `python3 scripts/task.py block {id} "причина" --kind needs_input`
и остановись.
Никогда не ослабляй проверки."""

LIGHT = """
Лёгкий путь (тривиальная задача): не запускай субагентов reviewer и explorer;
начни с `just context <модуль>` и читай только нужные фрагменты;
во время работы проверяй `just test-module <модуль>`; отдельный `just verify` не нужен —
`python3 scripts/task.py done {id}` сам прогонит полный verify.
Если меняется поведение или публичный API — обнови карточку модуля docs/modules/<модуль>.md."""


def sh(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def bd_json(*args: str) -> Any:
    out = sh("bd", *args, "--json")
    try:
        return json.loads(out)
    except ValueError:
        return None


def bd_items(*args: str) -> list[dict[str, Any]]:
    """bd --json всегда нормализуется в список объектов."""
    data = bd_json(*args)
    raw = cast("list[Any]", data if isinstance(data, list) else [data])
    return [x for x in raw if isinstance(x, dict)]


def task_info(task_id: str) -> dict[str, str]:
    # для неизвестного id bd отдаёт JSON с ошибкой, а не пустой ответ — нужен настоящий id задачи
    items = [x for x in bd_items("show", task_id) if x.get("id") == task_id]
    if not items:
        sys.exit(f"задача {task_id} не найдена (bd show) — сессия не запускается")
    item = items[0]
    return {"id": task_id, "title": str(item.get("title")), "status": str(item.get("status"))}


def pick_task() -> str:
    for args in (("list", "--status", "in_progress"), ("ready",)):
        items = bd_items(*args)
        if items:
            return str(items[0]["id"])
    sys.exit("нет задач в работе и готовых к работе (bd ready пуст)")


def fingerprint(task_id: str) -> str:
    progress = ROOT / "tasks" / task_id / "PROGRESS.md"
    body = progress.read_bytes() if progress.exists() else b""
    return sh("git", "rev-parse", "HEAD") + hashlib.sha256(body).hexdigest()


def allowed_tools() -> list[str]:
    try:
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    except (OSError, ValueError):
        return []
    return [str(x) for x in settings.get("permissions", {}).get("allow", [])]


def backend_env(backend: str, model: str) -> dict[str, str]:
    env = dict(os.environ)
    if backend != "ollama":
        return env
    key = env.pop("OLLAMA_API_KEY", "")
    if not key and OLLAMA_ENV.exists():
        for line in OLLAMA_ENV.read_text().splitlines():
            if line.startswith("OLLAMA_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit(f"нет OLLAMA_API_KEY ({OLLAMA_ENV})")
    env.pop("ANTHROPIC_API_KEY", None)
    env.update(
        ANTHROPIC_BASE_URL="https://ollama.com",
        ANTHROPIC_AUTH_TOKEN=key,
        ANTHROPIC_DEFAULT_OPUS_MODEL=model,
        ANTHROPIC_DEFAULT_SONNET_MODEL=model,
        ANTHROPIC_DEFAULT_HAIKU_MODEL=model,
        CLAUDE_CODE_SUBAGENT_MODEL=model,
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
    )
    return env


def otel_settings(task_id: str) -> str:
    """Метка задачи в телеметрии: --settings имеет приоритет над env проекта."""
    meta = metrics.task_meta(task_id)
    attrs = (
        f"project={metrics.project_slug()},task={task_id},task_type={meta['type']},"
        f"risk={meta['risk']},harness={metrics.harness_version()}"
    )
    return json.dumps({"env": {"OTEL_RESOURCE_ATTRIBUTES": attrs}})


def run_session(prompt: str, args: argparse.Namespace) -> dict[str, object]:
    session_id = str(uuid.uuid4())
    cmd = [
        "claude", "-p", prompt,
        "--model", args.model,
        "--max-budget-usd", str(args.session_budget),
        "--output-format", "json",
        "--session-id", session_id,
        "--settings", otel_settings(args.task_id),
        "--permission-mode", "acceptEdits",
        "--allowedTools", *allowed_tools(), "Edit", "Write", "Read", "Grep", "Glob", "Task",
    ]  # fmt: skip
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True, env=backend_env(args.backend, args.model),
    )  # fmt: skip
    timed_out = False
    try:
        out, err = proc.communicate(timeout=args.session_timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        out, err = proc.communicate()
        timed_out = True
    record: dict[str, object] = {
        "duration_s": round(time.monotonic() - start),
        "exit": proc.returncode,
        "timed_out": timed_out,
        "session_id": session_id,
        **metrics.session_stats(session_id),
    }
    try:
        result = json.loads(out)
        record.update(
            cost_usd=result.get("total_cost_usd"),
            turns=result.get("num_turns"),
            subtype=result.get("subtype"),
            is_error=result.get("is_error"),
            result=str(result.get("result", ""))[:500],
        )
    except ValueError:
        record["error"] = (err or out)[-500:]
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--backend", choices=["anthropic", "ollama"], default="anthropic")
    parser.add_argument("--model")
    parser.add_argument("--session-budget", type=float, default=2.0)
    parser.add_argument("--total-budget", type=float, default=6.0)
    parser.add_argument("--session-timeout", type=int, default=1800)
    parser.add_argument("--max-sessions", type=int, default=5)
    parser.add_argument("--max-idle", type=int, default=2)
    parser.add_argument(
        "--path", choices=["full", "light"], help="по умолчанию: light для trivial, иначе full"
    )
    args = parser.parse_args()
    args.model = args.model or (OLLAMA_MODEL if args.backend == "ollama" else "sonnet")

    task_id = args.task or pick_task()
    args.task_id = task_id
    meta = metrics.task_meta(task_id)
    # мини-эксперимент 2026-09-24 (PLAN): на trivial лёгкий путь вдвое дешевле при том же результате
    args.path = args.path or ("light" if meta["risk"] == "trivial" else "full")
    spent, idle, reason = 0.0, 0, "max-sessions"
    RUNS.parent.mkdir(exist_ok=True)
    for n in range(1, args.max_sessions + 1):
        info = task_info(task_id)
        if info["status"] in {"closed", "blocked"}:
            reason = info["status"]
            break
        if spent >= args.total_budget:
            reason = "total-budget"
            break
        before = fingerprint(task_id)
        print(f"── сессия {n}: {task_id} ({info['status']}), потрачено ${spent:.2f}", flush=True)
        prompt = PROMPT + (LIGHT if args.path == "light" else "")
        record = run_session(prompt.format(**info), args)
        cost = record.get("cost_usd")
        # при таймауте стоимость неизвестна — считаем по верхней границе
        spent += float(cost) if isinstance(cost, int | float) else args.session_budget
        idle = 0 if fingerprint(task_id) != before else idle + 1
        record.update(
            ts=datetime.now(UTC).isoformat(timespec="seconds"),
            backend=args.backend,
            model=args.model,
            task=task_id,
            task_type=meta["type"],
            risk=meta["risk"],
            path=args.path,
            harness=metrics.harness_version(),
            session_n=n,
            spent_total=round(spent, 4),
            progressed=idle == 0,
        )
        with RUNS.open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"   {json.dumps(record, ensure_ascii=False)[:400]}", flush=True)
        if idle >= args.max_idle:
            reason = f"no-progress x{idle}"
            break
    else:
        reason = "max-sessions"
    final = task_info(task_id)["status"]
    if final in {"closed", "blocked"}:
        reason = final
    elif reason == "max-sessions":
        reason += " → задача в работе, продолжить: запустите agent_run снова"
    else:
        # исчерпан общий бюджет или нет прогресса — без человека продолжать бессмысленно
        kind = "no_progress" if reason.startswith("no-progress") else "budget"
        subprocess.run(
            [sys.executable, "scripts/task.py", "block", task_id,
             f"agent_run остановлен: {reason} (потрачено ≈ ${spent:.2f})", "--kind", kind],
            cwd=ROOT, check=False,
        )  # fmt: skip
        reason += f" → задача blocked [{kind}], нужен человек"
    print(f"\nитог: задача {task_id} = {final}; остановка: {reason}; потрачено ≈ ${spent:.2f}")
    return 0 if final == "closed" else 1


if __name__ == "__main__":
    sys.exit(main())
