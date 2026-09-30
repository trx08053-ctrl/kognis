#!/usr/bin/env python3
"""Единая проверка проекта и запись доказательства (evidence).

    verify.py              все проверки; при успехе пишет .evidence/<tree>.json
    verify.py lint tests   только выбранные проверки (evidence не пишется)
    verify.py --status     exit 0, если для текущего дерева есть успешное evidence
    verify.py --list       список проверок

<tree> — git tree-hash рабочей копии, включая неотслеживаемые файлы (кроме .gitignore),
поэтому любое изменение кода после проверки делает evidence устаревшим.
Состояние задач (STATE_PATHS: .beads/, tasks/) в хэш не входит: обновление прогресса
после проверки не делает её недействительной.
Файл защищён: изменять только с одобрения человека.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / ".evidence"
ATTEMPTS = EVIDENCE / "attempts.json"
MAX_ATTEMPTS = 3
STATE_PATHS = [".beads", "tasks"]
LOGS = EVIDENCE / "logs"
# вывод проверок в контекст агента — только итог и суть падений; полный поток: verify.py -v
VERBOSE = "-v" in sys.argv[1:] or os.environ.get("VERIFY_VERBOSE") == "1"

PY = sys.executable
# ruff — только каталоги с кодом (не «.»: в песочнице Claude служебные пути — нечитаемые заглушки)
CODE_DIRS = [
    d for d in ("src", "tests", "scripts", ".claude/hooks", "migrations") if (ROOT / d).exists()
]
# (имя, команда, включена ли) — arch/map включаются, если в проекте есть их конфигурация (профиль M)
ALL_CHECKS: list[tuple[str, list[str], bool]] = [
    ("format", ["uv", "run", "--locked", "ruff", "format", "--check", *CODE_DIRS], True),
    (
        "lint",
        ["uv", "run", "--locked", "ruff", "check", "--output-format", "concise", *CODE_DIRS],
        True,
    ),
    ("types", ["uv", "run", "--locked", "basedpyright"], True),
    ("arch", ["uv", "run", "--locked", "lint-imports"], (ROOT / ".importlinter").exists()),
    ("boundaries", [PY, "scripts/check_boundaries.py"], (ROOT / ".importlinter").exists()),
    # ARCHITECTURE.md (таблица модулей, владение таблицами, диаграмма) не расходится с кодом
    ("arch-doc", [PY, "scripts/check_arch_doc.py"], (ROOT / ".importlinter").exists()),
    ("migrations", [PY, "scripts/check_migrations.py"], (ROOT / "alembic.ini").exists()),
    # контракт API: типы фронтенда (api.gen.ts) сгенерированы из текущей схемы OpenAPI бэкенда
    (
        "contract",
        [PY, "scripts/gen_api_types.py", "--check"],
        (ROOT / "scripts" / "gen_api_types.py").exists(),
    ),
    # фронтенд: Biome, tsc strict, vitest + покрытие, сборка dist (её открывают e2e-тесты)
    ("frontend", ["pnpm", "--dir", "frontend", "run", "check"], (ROOT / "frontend").is_dir()),
    ("tests", ["uv", "run", "--locked", "pytest"], True),
    ("ratchet", [PY, "scripts/check_ratchet.py"], True),
    ("size", [PY, "scripts/check_size.py"], True),
    # мультиязычность: текст для человека — только в словарях (docs/I18N.md); для веб-проектов
    ("i18n", [PY, "scripts/check_i18n.py"], any((ROOT / "src").glob("*/web"))),
    # безопасность: Semgrep (harness + OWASP) по коду, osv-scanner по lockfile — docs/SECURITY.md
    ("sast", [PY, "scripts/check_security.py", "sast"], True),
    ("deps", [PY, "scripts/check_security.py", "deps"], True),
    ("no-weakening", [PY, "scripts/check_no_weakening.py"], True),
    ("secrets", ["gitleaks", "dir", ".", "--no-banner", "--redact", "-c", ".gitleaks.toml"], True),
    ("map", [PY, "scripts/gen_map.py", "--check"], (ROOT / "docs" / "MAP.md").exists()),
    ("refs", [PY, "scripts/check_refs.py"], True),
    # ссылки документации; HTML-шаблоны приложения (src/, frontend/) — не документация
    (
        "docs",
        [
            "lychee",
            "--offline",
            "--no-progress",
            "--exclude-path",
            ".venv",
            "--exclude-path",
            "src",
            "--exclude-path",
            "frontend",
            "--exclude-path",
            "mutants",
            ".",
        ],
        True,
    ),
]
CHECKS: list[tuple[str, list[str]]] = [(n, c) for n, c, on in ALL_CHECKS if on]

TOOLS = ["python3", "uv", "ruff", "basedpyright", "gitleaks", "lychee", "osv-scanner"] + (
    ["node", "pnpm"] if (ROOT / "frontend").is_dir() else []
)


def git(*args: str, env: dict[str, str] | None = None) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def tree_hash() -> str:
    """Хэш дерева рабочей копии без изменения настоящего индекса."""
    index = ROOT / git("rev-parse", "--git-path", "index")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_index = Path(tmp) / "index"
        if index.exists():
            shutil.copy(index, tmp_index)
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
        git("add", "-u", env=env)
        # только обычные файлы и ссылки: песочница Claude подставляет /dev/null на месте
        # несуществующих служебных путей (.bashrc, .mcp.json, .claude/commands…)
        others = [
            p for p in git("ls-files", "-z", "--others", "--exclude-standard").split("\0") if p
        ]
        regular = [p for p in others if is_regular(ROOT / p)]
        for i in range(0, len(regular), 500):
            git("add", "--", *regular[i : i + 500], env=env)
        git("rm", "-r", "--cached", "-q", "--ignore-unmatch", *STATE_PATHS, env=env)
        return git("write-tree", env=env)


def is_regular(path: Path) -> bool:
    mode = path.lstat().st_mode
    return stat.S_ISREG(mode) or stat.S_ISLNK(mode)


def head() -> str:
    try:
        return git("rev-parse", "HEAD")
    except subprocess.CalledProcessError:
        return "(no commits)"


def tool_version(tool: str) -> str:
    cmd = ["uv", "run", "--locked", tool] if tool in {"ruff", "basedpyright"} else [tool]
    try:
        out = subprocess.run(
            [*cmd, "--version"], cwd=ROOT, capture_output=True, text=True, timeout=30, check=False
        )
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return "unavailable"


def load_attempts() -> dict[str, dict[str, object]]:
    try:
        data = json.loads(ATTEMPTS.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


NOISE = re.compile(
    r"\d+(\.\d+)?\s*(s|ms|sec|seconds)\b|\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?|0x[0-9a-f]+"
    r"|/tmp/\S+|\b[0-9a-f]{12,}\b|\x1b\[[0-9;]*m"
)


def signature(output: str) -> str:
    """Отпечаток причины падения: хвост вывода без времени, длительностей, адресов и хэшей."""
    tail = [NOISE.sub("", line).strip() for line in output.strip().splitlines()[-30:]]
    return hashlib.sha256("\n".join(x for x in tail if x).encode()).hexdigest()[:16]


def run_check(cmd: list[str], stream: bool = False) -> tuple[int, str]:
    """Запустить проверку: вывод сохраняется (журнал, отпечаток), на экран — только с -v.

    Окружение как в CI (UTC): иначе покрытие и поведение кода с датами зависят от пояса машины,
    и планка, поднятая локально, падает в CI (kognis: ветвления 81,9 % в МСК и 80,8 % в UTC).
    """
    env = {**os.environ, "TZ": "UTC"}
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    lines: list[str] = []
    if proc.stdout is None:
        return proc.wait(), ""
    for line in proc.stdout:
        if stream:
            print(line, end="", flush=True)
        lines.append(line)
    return proc.wait(), "".join(lines)


FAIL_TAIL = 40
FAIL_HINT = re.compile(r"FAIL|Error|error|assert|✗|×|E\s{3}|Would reformat|^\S+:\d+:\d*:? ", re.M)


def failure_excerpt(output: str) -> str:
    """Суть падения без простыни: строки с признаками ошибки и хвост вывода.

    В хвосте итог большинства инструментов (причина ratchet, таблица уязвимостей).
    """
    lines = [ln for ln in output.splitlines() if ln.strip()]
    hits = [i for i, ln in enumerate(lines) if FAIL_HINT.search(ln)][-FAIL_TAIL // 2 :]
    tail = list(range(max(0, len(lines) - FAIL_TAIL // 2), len(lines)))
    picked = sorted(set(hits) | set(tail))
    return "\n".join(f"    {lines[i][:300]}" for i in picked)


def harness_version() -> str:
    answers = ROOT / ".copier-answers.yml"
    match = re.search(r"^_commit:\s*(\S+)", answers.read_text(), re.M) if answers.exists() else None
    return match.group(1) if match else "unknown"


def status() -> int:
    path = EVIDENCE / f"{tree_hash()}.json"
    if path.exists() and json.loads(path.read_text()).get("ok"):
        print(f"verified: {path.relative_to(ROOT)}")
        return 0
    print("NOT verified: нет успешного evidence для текущего состояния кода")
    return 1


def run_one(
    name: str, cmd: list[str], attempts: dict[str, dict[str, object]]
) -> tuple[dict[str, object], str]:
    """Одна проверка: журнал в .evidence/logs, краткий итог на экран, учёт повторов причины."""
    if VERBOSE:
        print(f"── {name}: {' '.join(cmd)}", flush=True)
    start = time.monotonic()
    code, output = run_check(cmd, stream=VERBOSE)
    duration = round(time.monotonic() - start, 1)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    log.write_text(f"$ {' '.join(cmd)}\n{output}")
    if not VERBOSE:
        print(f"  {'ok  ' if code == 0 else 'FAIL'} {name} ({duration}s)", flush=True)
        if code != 0:
            print(failure_excerpt(output))
            print(f"    … полный вывод: {log.relative_to(ROOT)}", flush=True)
    if code == 0:
        attempts.pop(name, None)
    else:
        # повтор той же причины = застревание; новая причина = продвижение отладки
        sig, prev = signature(output), attempts.get(name, {})
        repeats = int(str(prev.get("repeats", 0))) + 1 if prev.get("sig") == sig else 1
        attempts[name] = {"sig": sig, "repeats": repeats}
    result: dict[str, object] = {
        "name": name,
        "cmd": " ".join(cmd),
        "exit": code,
        "duration_s": duration,
    }
    return result, output


def run(selected: list[str]) -> int:
    names = [n for n, _ in CHECKS]
    unknown = [s for s in selected if s not in names]
    if unknown:
        print(f"неизвестные проверки: {unknown}; доступны: {names}")
        return 2
    full = not selected
    tree = tree_hash()
    attempts = load_attempts()
    results: list[dict[str, object]] = []
    tests_summary = ""

    for name, cmd in CHECKS:
        if not full and name not in selected:
            continue
        result, output = run_one(name, cmd, attempts)
        results.append(result)
        if name == "tests":
            summary = [ln for ln in output.splitlines() if re.search(r"\d+ (passed|failed)", ln)]
            tests_summary = summary[-1].strip("= ") if summary else ""

    EVIDENCE.mkdir(exist_ok=True)
    ATTEMPTS.write_text(json.dumps(attempts, indent=2))
    failed = [r["name"] for r in results if r["exit"] != 0]

    if VERBOSE:  # в компактном режиме строки уже напечатаны по ходу
        print(
            "\n"
            + "\n".join(
                f"  {'ok  ' if r['exit'] == 0 else 'FAIL'} {r['name']} ({r['duration_s']}s)"
                for r in results
            )
        )
    stuck = [
        n for n in failed if int(str(attempts.get(str(n), {}).get("repeats", 0))) >= MAX_ATTEMPTS
    ]
    if stuck:
        print(
            f"\nESCALATE: {stuck} падают {MAX_ATTEMPTS}+ раз подряд с одной и той же причиной — "
            "отладка не продвигается. Остановись: диагноз и гипотезы в PROGRESS.md, "
            'just task-block <id> "…" --kind needs_input. Ослаблять проверки запрещено.'
        )

    if not full:
        print("\n(частичный прогон — evidence не записан; для статуса «готово» нужен just verify)")
        return 1 if failed else 0
    if failed:
        print(f"\nverify FAILED: {failed} — evidence не записан")
        return 1
    if tree_hash() != tree:
        print(
            "\nverify: файлы изменились во время проверки — evidence не записан, запустите заново"
        )
        return 1

    head_sha = head()
    evidence: dict[str, object] = {
        "ok": True,
        "tree": tree,
        "head": head_sha,
        "dirty": bool(git("status", "--porcelain")),
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "harness": harness_version(),
        "tests": tests_summary,
        "checks": results,
        "tool_versions": {t: tool_version(t) for t in TOOLS},
        "note": "подсказка агенту; допуск — повторный verify в task-done и CI",
    }
    path = EVIDENCE / f"{tree}.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False))
    (EVIDENCE / "latest.json").write_text(path.read_text())
    print(
        f"\nverify OK · tree {tree[:12]} · head {head_sha[:12]} · evidence {path.relative_to(ROOT)}"
    )
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "-v"]
    if args == ["--status"]:
        return status()
    if args == ["--list"]:
        print("\n".join(n for n, _ in CHECKS))
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
