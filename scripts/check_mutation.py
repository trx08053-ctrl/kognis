#!/usr/bin/env python3
"""Мутационное тестирование изменений задачи: ловят ли тесты поломку кода. Файл защищён.

    check_mutation.py <task-id>   мутанты функций, изменённых коммитами задачи ([<task-id>])

mutmut портит код (условия, числа, операторы) и прогоняет тесты: «выживший» мутант — поломка,
которую тесты не заметили. Мутируется только бизнес-логика (`_domain.py`, `_app.py`) изменённых
функций — быстро и по делу; e2e и integration не запускаются. Порог — доля пойманных ≥ MIN_SCORE.
Эквивалентный мутант (поведение не меняется) — комментарий pragma «no mutate» с `justified:`.
Запускается в `task-done` для risky-задач и вручную: `just mutate <id>`.
"""

from __future__ import annotations

import ast
import fnmatch
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_SCORE = 0.8
LOGIC_FILES = re.compile(r"^src/[^/]+/[^/]+/_(domain|app)\.py$")
SHOW_SURVIVORS = 15


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout


def changed_functions(task_id: str) -> dict[str, set[str]]:
    """{модуль: {имя функции/метода}} — функции, строки которых меняли коммиты задачи."""
    result: dict[str, set[str]] = {}
    for sha in git("log", "--format=%H", "--fixed-strings", f"--grep=[{task_id}]").split():
        for path in git("show", "--name-only", "--format=", sha).split():
            # только бизнес-модули (с _domain.py): web и платформа покрыты integration/e2e
            if (
                not LOGIC_FILES.match(path)
                or not (ROOT / Path(path).parent / "_domain.py").exists()
            ):
                continue
            lines = changed_lines(sha, path)
            source = git("show", f"{sha}:{path}")
            if not lines or not source:
                continue
            module = path.removeprefix("src/").removesuffix(".py").replace("/", ".")
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    end = node.end_lineno or node.lineno
                    if any(node.lineno <= n <= end for n in lines):
                        result.setdefault(module, set()).add(node.name)
    return result


def changed_lines(sha: str, path: str) -> set[int]:
    lines: set[int] = set()
    for match in re.finditer(
        r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", git("show", "-U0", sha, "--", path), re.M
    ):
        start, count = int(match.group(1)), int(match.group(2) or "1")
        lines.update(range(start, start + max(count, 1)))
    return lines


def patterns(functions: dict[str, set[str]]) -> list[str]:
    return sorted(
        pattern
        for module, names in functions.items()
        for name in names
        for pattern in (f"{module}.x_{name}__mutmut_*", f"{module}.xǁ*ǁ{name}__mutmut_*")
    )


def statuses(globs: list[str]) -> dict[str, str]:
    out = subprocess.run(
        ["uv", "run", "--locked", "mutmut", "results", "--all", "true"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout  # fmt: skip
    found: dict[str, str] = {}
    for line in out.splitlines():
        name, _, status = line.strip().partition(": ")
        if status and any(fnmatch.fnmatchcase(name, g) for g in globs):
            found[name] = status.strip()
    return found


def main() -> int:
    if len(sys.argv) != 2:  # noqa: PLR2004  justified: harness-mut one positional argument
        print(__doc__)
        return 2
    task_id = sys.argv[1]
    functions = changed_functions(task_id)
    if not functions:
        print(
            f"мутации: в коммитах [{task_id}] нет изменённой бизнес-логики (_domain/_app) — пропуск"
        )
        return 0
    globs = patterns(functions)
    count = sum(len(v) for v in functions.values())
    print(f"── мутации: {count} функций в {len(functions)} модулях", flush=True)
    start = time.monotonic()
    subprocess.run(["uv", "run", "--locked", "mutmut", "run", *globs], cwd=ROOT,
                   capture_output=True, check=False)  # fmt: skip
    found = statuses(globs)
    counted = {n: s for n, s in found.items() if s not in {"skipped", "not checked"}}
    killed = [n for n, s in counted.items() if s in {"killed", "timeout", "segfault"}]
    survived = sorted(n for n in counted if n not in killed)
    score = len(killed) / len(counted) if counted else 1.0
    elapsed = round(time.monotonic() - start)
    print(f"мутанты: {len(counted)}, пойманы {len(killed)}, выжили {len(survived)}; "
          f"доля {score:.0%} (порог {MIN_SCORE:.0%}), {elapsed} с")  # fmt: skip
    for name in survived[:SHOW_SURVIVORS]:
        diff = subprocess.run(["uv", "run", "--locked", "mutmut", "show", name], cwd=ROOT,
                              capture_output=True, text=True, check=False).stdout  # fmt: skip
        change = [ln for ln in diff.splitlines() if re.match(r"^[-+](?![-+])", ln)]
        print(f"  выжил {name.split('.')[-1]} ({counted[name]}):\n    " + "\n    ".join(change[:4]))
    if score < MIN_SCORE:
        print(
            "Тесты не замечают эти поломки: добавь проверки (граничные значения, ветки), а не "
            "подгоняй код. Эквивалентный мутант — комментарий pragma «no mutate» с `justified:`."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
