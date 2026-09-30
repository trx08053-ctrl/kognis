#!/usr/bin/env python3
"""PreToolUse: защищает файлы проверок и запрещает обход git hooks.

- Edit/Write защищённого файла → решение человека (permissionDecision=ask).
- Bash, который пишет в защищённый файл → ask.
- Обход проверок (--no-verify, LEFTHOOK=0, push --force) → deny.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

PROTECTED = [
    "pyproject.toml",
    "uv.lock",
    "justfile",
    "lefthook.yml",
    "mise.toml",
    ".gitleaks.toml",
    "cliff.toml",
    ".sops.yaml",
    ".importlinter",
    ".dependency-cruiser.cjs",
    "scripts/verify.py",
    "scripts/check_*.py",
    "scripts/task.py",
    "scripts/agent_run.py",
    "scripts/second_opinion.py",
    "scripts/gen_map.py",
    "scripts/new_module.py",
    "scripts/worktree.py",
    "scripts/costs.py",
    "scripts/context.py",
    "scripts/locate.py",
    "scripts/test_module.py",
    "scripts/regress.py",
    "scripts/metrics.py",
    "scripts/ui_feedback.py",
    "scripts/ui_overlay.js",
    "scripts/web.py",
    "Dockerfile",
    "deploy/compose.yml",
    "alembic.ini",
    "web.just",
    "frontend.just",
    "frontend/package.json",
    "frontend/pnpm-lock.yaml",
    "frontend/tsconfig.json",
    "frontend/biome.json",
    "frontend/vite.config.ts",
    "frontend/src/vitest.setup.ts",
    "frontend/src/api.gen.ts",
    ".claude/settings.json",
    ".claude/hooks/*",
    ".github/*",
    ".github/**/*",
    ".copier-answers.yml",
    "security/*",
    ".trivyignore",
    ".zap-rules.tsv",
    ".quality-baseline.json",
]
BYPASS = re.compile(
    r"--no-verify|\bgit\s+commit\b[^|;&]*\s-n\b|LEFTHOOK=0|LEFTHOOK_EXCLUDE"
    r"|\bgit\s+push\b[^|;&]*(--force\b|\s-f\b)|core\.hooksPath"
)
# Операции, безвозвратно выбрасывающие незакоммиченную работу — всегда через человека
DESTRUCTIVE_GIT = re.compile(
    r"\bgit\s+(checkout\s+(\S+\s+)*--(\s|$)|checkout\s+\.(\s|$)|restore\b|reset\s+--hard|clean\s+-\w*f"
    r"|stash\s+(drop|clear)|branch\s+-D)"
)
WRITE_OPS = re.compile(r"(\bsed\s+-i|\bperl\s+-i|>>?|\btee\b|\bmv\b|\bcp\b|\brm\b|\btruncate\b)")
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}


def write_targets(cmd: str) -> list[str] | None:
    """Файлы, в которые пишет команда (цели >, tee, cp/mv, rm, sed -i…); None — не разобрали.

    Текст в кавычках — данные: `task.py block id "a > b"` ничего не перезаписывает.
    """
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    targets: list[str] = []
    words: list[str] = []
    for i, tok in enumerate([*tokens, ";"]):
        if tok in {">", ">>", ">|"} and i + 1 < len(tokens):
            targets.append(tokens[i + 1])
        if tok not in SEPARATORS:
            words.append(tok)
            continue
        targets += command_targets(words)
        words = []
    return targets


def command_targets(words: list[str]) -> list[str]:
    while words and re.fullmatch(r"\w+=.*", words[0]):  # VAR=value перед командой
        words = words[1:]
    if not words:
        return []
    name, args = Path(words[0]).name, [w for w in words[1:] if not w.startswith("-")]
    flags = [w for w in words[1:] if w.startswith("-")]
    if name in {"tee", "rm", "truncate", "shred", "mv"}:  # mv меняет и источник, и назначение
        return args
    if name in {"cp", "install", "ln"}:
        return args[-1:]
    if name in {"sed", "perl"} and any(f.startswith("-i") or "i" in f.lstrip("-") for f in flags):
        return args[1:] if "-e" not in flags else args
    return []


def checkout_discards_files(cmd: str, root: Path) -> bool:
    """`git checkout <путь>` без `--` тоже выбрасывает изменения файла — отличаем от смены ветки."""
    for segment in re.split(r"&&|\|\||;|\|", cmd):
        try:
            words = shlex.split(segment)
        except ValueError:
            continue
        if words[:2] != ["git", "checkout"] or {"-b", "-B", "--orphan"} & set(words):
            continue
        if any((root / w).exists() for w in words[2:] if not w.startswith("-")):
            return True
    return False


def decide(decision: str, reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


def is_protected(path: str, root: Path) -> str | None:
    try:
        rel = str(Path(path).resolve().relative_to(root))
    except ValueError:
        return None
    return next((p for p in PROTECTED if fnmatch.fnmatch(rel, p)), None)


def main() -> None:
    data = json.load(sys.stdin)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", "."))).resolve()
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {})

    if tool == "Bash":
        cmd = str(inp.get("command", ""))
        if BYPASS.search(cmd):
            decide(
                "deny",
                "Обход git hooks / force-push запрещён (AGENTS.md). "
                "Исправь причину падения проверки или эскалируй человеку.",
            )
        if re.search(r"\bjust\s+land\b|scripts/land\.py", cmd):
            decide("ask", "Перенос в main (land) — решение человека (AGENTS.md).")
        if re.search(r"\bjust\s+i18n-adopt\b|check_i18n\.py\s+--adopt", cmd):
            decide("ask", "Фиксация долга перевода в планке (i18n-adopt) — решение человека.")
        if DESTRUCTIVE_GIT.search(cmd) or checkout_discards_files(cmd, root):
            decide(
                "ask",
                "Команда может безвозвратно выбросить незакоммиченную работу (checkout --/restore/"
                "reset --hard/clean). Нужно решение человека; сначала сохрани изменения "
                "(коммит в ветку).",
            )
        targets = write_targets(cmd)
        if targets is None and WRITE_OPS.search(cmd):  # не разобрали — осторожно, как раньше
            hit = next((p for p in PROTECTED if "*" not in p and p in cmd), None)
        else:
            hit = next((h for t in targets or [] if (h := is_protected(str(root / t), root))), None)
            if hit:
                decide(
                    "ask",
                    f"Команда может изменить защищённый файл {hit}. "
                    "Изменение проверок требует решения человека.",
                )
        return

    path = inp.get("file_path") or inp.get("notebook_path")
    if path and (hit := is_protected(str(path), root)):
        decide(
            "ask",
            f"{path} защищён (шаблон {hit}): это конфигурация проверок/harness. "
            "Изменение требует решения человека. Не ослабляй проверки ради прохождения.",
        )


if __name__ == "__main__":
    main()
