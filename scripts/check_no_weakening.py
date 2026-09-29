#!/usr/bin/env python3
"""Запрещает ослаблять проверки без обоснования.

Ищет в ДОБАВЛЕННЫХ строках (относительно main или HEAD) подавления проверок:
noqa, type: ignore, pyright: ignore, pytest skip/xfail, eslint-disable, ts-ignore, .only(...).
Подавление допустимо только с пометкой в той же строке: `justified: <task-id> <причина>`.
Удаление assert/test-функций в tests/ выводится как предупреждение для ревьюера.

    check_no_weakening.py           рабочая копия против merge-base с main (или HEAD)
    check_no_weakening.py --staged  только staged-изменения (для pre-commit)

Файл защищён: изменять только с одобрения человека.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = "scripts/check_no_weakening.py"
SKIP_SUFFIXES = (".md", ".jsonl", ".lock")

SUPPRESSIONS = re.compile(
    r"#\s*noqa|#\s*type:\s*ignore|#\s*pyright:\s*ignore|#\s*pragma:\s*no\s*(cover|mutate)"
    r"|pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail)\("
    r"|eslint-disable|biome-ignore|(#|//)\s*nosemgrep|@ts-ignore|@ts-expect-error|@ts-nocheck"
    r"|\b(it|test|describe)\.(only|skip)\("
)
JUSTIFIED = re.compile(r"justified:\s*[\w.-]+-\w+")
REMOVED_TEST = re.compile(r"^\s*(assert\b|def test_|async def test_)")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout


def base_ref() -> str:
    for ref in ("origin/main", "main"):
        if git("rev-parse", "--verify", "--quiet", ref).strip():
            branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
            if branch != "main":
                return git("merge-base", "HEAD", ref).strip() or "HEAD"
    return "HEAD" if git("rev-parse", "--verify", "--quiet", "HEAD").strip() else ""


def diff(staged: bool) -> str:
    if staged:
        return git("diff", "--cached", "-U0", "--no-color")
    base = base_ref()
    if not base:  # репозиторий без коммитов: всё содержимое считается добавленным
        return git("diff", "--cached", "-U0", "--no-color") + untracked()
    return git("diff", base, "-U0", "--no-color") + untracked()


def untracked() -> str:
    parts: list[str] = []
    for name in git("ls-files", "--others", "--exclude-standard").splitlines():
        path = ROOT / name
        try:
            lines = path.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        parts.append(f"+++ b/{name}\n" + "\n".join(f"+{line}" for line in lines))
    return "\n".join(parts)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    current = ""
    for line in diff("--staged" in sys.argv).splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
            continue
        if not current or current == SELF or current.endswith(SKIP_SUFFIXES):
            continue
        if line.startswith("+") and SUPPRESSIONS.search(line) and not JUSTIFIED.search(line):
            errors.append(f"{current}: {line[1:].strip()}")
        elif (
            line.startswith("-")
            and not line.startswith("---")
            and current.startswith("tests/")
            and REMOVED_TEST.search(line[1:])
        ):
            warnings.append(f"{current}: удалено `{line[1:].strip()}`")

    for w in warnings:
        print(f"WARN (для ревьюера): {w}")
    if errors:
        print(
            "Подавление проверок без обоснования (добавьте `justified: <task-id> <причина>` "
            "или исправьте код; ослаблять проверки ради прохождения запрещено):"
        )
        for e in errors:
            print(f"  {e}")
        return 1
    print("no-weakening: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
