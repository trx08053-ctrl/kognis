#!/usr/bin/env python3
"""Затраты и ошибки агента по проекту.

    costs.py [--days 7]

Источники:
- .agent-log/runs.jsonl — автономные сессии agent_run (стоимость, ходы, таймауты, итог);
- .agent-log/YYYY-MM-DD.jsonl — журнал инструментов (вызовы и ошибки по инструментам);
- Prometheus стека наблюдаемости (http://127.0.0.1:9091, host/observability) — стоимость и токены
  всех сессий Claude Code с тегом project=<slug> (интерактивных тоже), если стек запущен.
Стоимость для не-Claude моделей (Ollama) — оценка Claude Code по прайсу Claude, не реальный счёт.
Файл защищён.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / ".agent-log"
PROM = os.environ.get("DEV_HARNESS_PROMETHEUS", "http://127.0.0.1:9091")


def project_slug() -> str:
    settings = (ROOT / ".claude" / "settings.json").read_text()
    match = re.search(r"project=([\w.-]+)", settings)
    return match.group(1) if match else ROOT.name


def load(path: Path, since: datetime) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [r for r in rows if datetime.fromisoformat(r["ts"]) >= since]


def num(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def runs(since: datetime) -> None:
    """По задачам: все попытки agent_run + исход; по типам — стоимость принятого результата."""
    sessions = load(LOG / "runs.jsonl", since)
    outcomes = load(LOG / "tasks.jsonl", since)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in sessions:
        by_task[str(r.get("task"))].append(r)
    final: dict[str, dict[str, Any]] = {str(o["task"]): o for o in outcomes}
    print("## По задачам (стоимость — оценка Claude Code; для подписки Ollama это не счёт)")
    print(
        f"  {'задача':16} {'тип/риск':18} {'исход':18} сесс.   $оц.  verify/падений"
        "  чтений файлов модули  чел.мин"
    )
    groups: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for task in sorted(set(by_task) | set(final)):
        rs, fin = by_task.get(task, []), final.get(task, {})
        kind = f"{fin.get('type') or (rs[0].get('task_type') if rs else '?')}/" + str(
            fin.get("risk") or (rs[0].get("risk") if rs else "?")
        )
        cost = sum(num(r.get("cost_usd")) for r in rs)
        vr, vf = (
            sum(num(r.get("verify_runs")) for r in rs),
            sum(num(r.get("verify_fails")) for r in rs),
        )
        reads = sum(num(r.get("reads")) for r in rs)
        outcome = str(fin.get("outcome", "в работе"))
        human = fin.get("human_min")
        print(
            f"  {task:16} {kind:18} {outcome:18} {len(rs):5} {cost:6.2f}  {int(vr):4}/{int(vf):<4}"
            f"          {int(reads):5} {fin.get('files_changed', '-')!s:>5}  "
            f"{','.join(fin.get('modules', [])) or '-':8} {human if human is not None else '-'}"
        )
        g = groups[kind]
        g["tasks"] += 1
        g["accepted"] += outcome == "accepted"
        g["cost"] += cost
        g["sessions"] += len(rs)
        g["verify_fails"] += vf
        g["human"] += num(human)
        g["human_n"] += human is not None
    if groups:
        print("\n## По типам задач (неудачные попытки входят в стоимость принятого результата)")
        for kind, g in sorted(groups.items()):
            per = g["cost"] / g["accepted"] if g["accepted"] else float("nan")
            hum = f"{g['human'] / g['human_n']:.0f}" if g["human_n"] else "-"
            print(
                f"  {kind:18} задач {int(g['tasks'])}, принято {int(g['accepted'])}, "
                f"$оц. на принятую {per:.2f}, сессий/задачу {g['sessions'] / g['tasks']:.1f}, "
                f"падений verify/задачу {g['verify_fails'] / g['tasks']:.1f}, чел.мин {hum}"
            )
        print("  (тенденции по задачам одного типа; один показатель не оценивает архитектуру)")


def tools(since: datetime) -> None:
    calls: Counter[str] = Counter()
    fails: Counter[str] = Counter()
    last_errors: list[str] = []
    for path in sorted(LOG.glob("20*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if datetime.fromisoformat(r["ts"]) < since:
                continue
            calls[r["tool"]] += 1
            if not r.get("ok", True):
                fails[r["tool"]] += 1
                last_errors.append(f"{r['ts']} {r['tool']}: {r.get('target', '')[:80]}")
    total = sum(calls.values())
    print(f"\n## Инструменты: вызовов {total}, ошибок {sum(fails.values())}")
    for tool, n in calls.most_common(10):
        print(f"  {tool:12} {n:5}  ошибок {fails[tool]}")
    for err in last_errors[-5:]:
        print(f"  ! {err}")


def prom(query: str) -> list[dict[str, Any]]:
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": query})
    if not url.startswith(("http://127.0.0.1", "http://localhost")):
        return []
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310  justified: harness-prom localhost only
        data: dict[str, Any] = json.loads(resp.read())
    result: list[dict[str, Any]] = data.get("data", {}).get("result", [])
    return result


def last(metric: str, selector: str, window: str) -> str:
    return f"max_over_time({metric}{{{selector}}}[{window}])"


def telemetry(days: int) -> None:
    slug = project_slug()
    print(f"\n## Телеметрия Claude Code (project={slug}, {days} дн.)")
    window = f"{days}d"
    # у каждой сессии свой ряд (session_id): последнее значение ряда = итог сессии
    sel = f'project="{slug}"'
    try:
        cost = prom(f"sum by (model) ({last('claude_code_cost_usage_USD_total', sel, window)})")
        tokens = prom(
            f"sum by (type) ({last('claude_code_token_usage_tokens_total', sel, window)})"
        )
        sessions = prom(f"count({last('claude_code_session_count_total', sel, window)})")
    except OSError:
        print("  стек наблюдаемости не запущен (см. host/observability в dev-harness)")
        return
    if sessions:
        print(f"  сессий: {int(float(sessions[0]['value'][1]))}")
    task_cost = last("claude_code_cost_usage_USD_total", sel + ',task!=""', window)
    by_task = prom(f"sum by (task) ({task_cost})")
    for row in sorted(by_task, key=lambda r: -float(r["value"][1]))[:10]:
        print(f"  задача {row['metric'].get('task')}: ${float(row['value'][1]):.2f} (оценка)")
    if not cost and not tokens:
        print("  данных нет (телеметрия не включена или ещё не экспортирована)")
    for row in cost:
        print(f"  ${float(row['value'][1]):.2f}  {row['metric'].get('model', '?')}")
    for row in tokens:
        print(f"  токенов {row['metric'].get('type', '?')}: {float(row['value'][1]):,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    since = datetime.now(UTC) - timedelta(days=args.days)
    runs(since)
    tools(since)
    telemetry(args.days)


if __name__ == "__main__":
    main()
