#!/usr/bin/env python3
"""Локальная проверка одного модуля: его тесты и архитектурные границы.

    test_module.py <модуль> [-- аргументы pytest]

Тесты модуля = tests/<модуль>/ + тесты, импортирующие модуль (по карте из кода). Показывает состав
проверок. Это быстрый цикл разработки; вердикт готовности — только `just verify` / `task-done`.
Файл защищён.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_map

ROOT = gen_map.ROOT


def main() -> int:
    argv = sys.argv[1:]
    extra = argv[argv.index("--") + 1 :] if "--" in argv else []
    name = argv[0] if argv and argv[0] != "--" else ""
    pkg, comps = gen_map.collect()
    comp = next((c for c in comps if c.name == name), None)
    if comp is None:
        sys.exit(f"нет модуля {name!r}; есть: {[c.name for c in comps]}")
    own = {p.relative_to(ROOT).as_posix() for p in (ROOT / "tests" / name).rglob("test_*.py")}
    tests = sorted(own | comp.tests)
    checks: list[tuple[str, list[str]]] = []
    if tests:
        checks.append(
            ("тесты", ["uv", "run", "--locked", "pytest", "--no-cov", "-q", *tests, *extra])
        )
    checks.append(("границы модулей", [sys.executable, "scripts/check_boundaries.py"]))
    if (ROOT / ".importlinter").exists():
        checks.append(("правила .importlinter", ["uv", "run", "--locked", "lint-imports"]))
    print(f"Проверки модуля {pkg}.{name}:")
    for t in tests:
        print(f"  тест: {t}{'  (свой)' if t in own else '  (использует модуль)'}")
    print("  + " + ", ".join(label for label, _ in checks[1:]))
    failed: list[str] = []
    for label, cmd in checks:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
        tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [""]
        print(f"  {'ok  ' if proc.returncode == 0 else 'FAIL'} {label}: {tail[0]}")
        if proc.returncode != 0:
            failed.append(label)
            print((proc.stdout + proc.stderr).strip()[-2000:])
    print("Локальная проверка. Вердикт готовности — just verify (task-done запускает его сам).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
