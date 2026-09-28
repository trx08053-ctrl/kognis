#!/usr/bin/env python3
"""Второе мнение на ревью от другой модели (OpenAI-совместимый API, по умолчанию Ollama Cloud).

    second_opinion.py [--task ID] [--base main] [--model deepseek-v4.1-flash]

Отправляет diff (base...рабочая копия) и TASK.md во внешний API — код покидает машину,
поэтому запускается только явно (`just review-x`). Ключ: OLLAMA_API_KEY в окружении или в
~/.config/dev-harness/ollama.env (путь — DEV_HARNESS_OLLAMA_ENV). Ключ не печатается.
Файл защищён.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = Path(
    os.environ.get("DEV_HARNESS_OLLAMA_ENV", "~/.config/dev-harness/ollama.env")
).expanduser()
BASE_URL = os.environ.get("SECOND_OPINION_URL", "https://ollama.com/v1")
MAX_DIFF_CHARS = 80_000
MAX_TOKENS = 16_000  # рассуждающие модели тратят часть лимита на reasoning

SYSTEM = """Ты — независимый строгий ревьюер кода. Проверяй только факты из diff.
Ищи: ошибки корректности и граничные случаи, нарушения критериев приёмки, ослабление проверок
(правки конфигов линтеров/тестов, удалённые assert, skip/noqa/ignore), уязвимости, нарушения
архитектурных границ, отсутствующие тесты и документацию. Не пересказывай diff.
Ответ строго в формате:
VERDICT: approve | request-changes
BLOCKERS:
- file:line — проблема — как исправить
MAJOR:
- ...
MINOR:
- ...
Если в разделе ничего нет — напиши «- нет». Если не уверен — пометь «(?)»."""


def api_key() -> str:
    key = os.environ.get("OLLAMA_API_KEY", "")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("OLLAMA_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit(f"нет OLLAMA_API_KEY (окружение или {ENV_FILE})")
    return key


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout


def collect(base: str, task: str | None) -> str:
    merge_base = git("merge-base", "HEAD", base).strip() or "HEAD"
    diff = git("diff", merge_base, "--", ".", ":(exclude)uv.lock", ":(exclude).beads")
    for name in git("ls-files", "--others", "--exclude-standard").splitlines():
        path = ROOT / name
        try:
            diff += f"\n--- /dev/null\n+++ b/{name}\n" + path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
    if not diff.strip():
        sys.exit("нет изменений относительно " + base)
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + f"\n… (обрезано, всего {len(diff)} символов)"
    parts = [f"## Diff относительно {base}\n```diff\n{diff}\n```"]
    task_file = ROOT / "tasks" / (task or "") / "TASK.md"
    if task and task_file.exists():
        parts.insert(0, f"## TASK.md\n{task_file.read_text()}")
    arch = ROOT / "docs" / "ARCHITECTURE.md"
    if arch.exists():
        parts.insert(0, f"## ARCHITECTURE.md\n{arch.read_text()}")
    return "\n\n".join(parts)


def ask(model: str, content: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": content},
            ],
            "max_tokens": MAX_TOKENS,
        }
    ).encode()
    if not BASE_URL.startswith("https://"):
        sys.exit("SECOND_OPINION_URL должен быть https://")
    request = urllib.request.Request(  # noqa: S310  justified: harness-https scheme checked above
        f"{BASE_URL}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310  justified: harness-https scheme checked above
            data: dict[str, Any] = json.loads(response.read())
    except urllib.error.HTTPError as err:
        sys.exit(f"API {err.code}: {err.read().decode()[:300]}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--base", default="main")
    parser.add_argument(
        "--model", default=os.environ.get("SECOND_OPINION_MODEL", "deepseek-v4.1-flash")
    )
    args = parser.parse_args()
    data = ask(args.model, collect(args.base, args.task))
    choices: list[dict[str, Any]] = data.get("choices") or [{}]
    choice = choices[0]
    message: dict[str, Any] = choice.get("message") or {}
    if not message:
        sys.exit(f"неожиданный ответ API: {json.dumps(data, ensure_ascii=False)[:300]}")
    usage = data.get("usage", {})
    print(
        f"# Второе мнение: {args.model} (токены: {usage.get('prompt_tokens')}→"
        f"{usage.get('completion_tokens')})\n"
    )
    print(str(message.get("content") or "(пустой ответ)").strip())
    if choice.get("finish_reason") == "length":
        print(f"\nВНИМАНИЕ: ответ обрезан по лимиту {MAX_TOKENS} токенов — результат неполный.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
