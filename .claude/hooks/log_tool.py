#!/usr/bin/env python3
"""PostToolUse / PostToolUseFailure: журнал действий агента в .agent-log/YYYY-MM-DD.jsonl.

Пишутся только метаданные (инструмент, цель, успех), без содержимого файлов и вывода.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

MAX = 300


def target(inp: dict[str, object]) -> str:
    for key in (
        "command",
        "file_path",
        "notebook_path",
        "pattern",
        "url",
        "query",
        "description",
        "subagent_type",
    ):
        if key in inp:
            return str(inp[key])[:MAX]
    return ""


def main() -> None:
    data = json.load(sys.stdin)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", ".")))
    resp = data.get("tool_response")
    failed = data.get("hook_event_name") == "PostToolUseFailure" or (
        isinstance(resp, dict) and bool(resp.get("is_error") or resp.get("interrupted"))
    )
    now = datetime.now(UTC)
    record = {
        "ts": now.isoformat(timespec="seconds"),
        "session": data.get("session_id", "")[:8],
        "tool": data.get("tool_name"),
        "target": target(data.get("tool_input") or {}),
        "ok": not failed,
    }
    if failed:
        record["error"] = str(data.get("error") or (resp or {}).get("stderr", ""))[:MAX]
    log_dir = root / ".agent-log"
    log_dir.mkdir(exist_ok=True)
    with (log_dir / f"{now:%Y-%m-%d}.jsonl").open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # журнал не должен ломать работу агента
        sys.exit(0)
