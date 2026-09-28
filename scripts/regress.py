#!/usr/bin/env python3
"""Воспроизводит ли регрессионный тест дефект на прежней реализации.

    regress.py <файл_теста> [...] [--ref HEAD]

Берёт тест(ы) из рабочей копии и запускает их на коде ref (по умолчанию HEAD — исправление ещё не
закоммичено; если закоммичено — --ref <коммит до исправления>) во временной рабочей копии.
Тест должен УПАСТЬ на старом коде — иначе он не проверяет исправленный дефект. Файл защищён.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tests", nargs="+")
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        old = Path(tmp) / "old"
        if run(["git", "worktree", "add", "-q", "--detach", str(old), args.ref], ROOT).returncode:
            sys.exit(f"не удалось создать рабочую копию {args.ref}")
        try:
            for test in args.tests:
                target = old / test
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / test, target)
            conftest = ROOT / "tests" / "conftest.py"
            if conftest.exists():
                shutil.copy(conftest, old / "tests" / "conftest.py")
            run(["uv", "sync", "--locked", "-q"], old)
            proc = run(["uv", "run", "--locked", "pytest", "--no-cov", "-q", *args.tests], old)
        finally:
            run(["git", "worktree", "remove", "--force", str(old)], ROOT)
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-5:])
    if proc.returncode != 0:
        print(f"OK: тест падает на {args.ref} — дефект воспроизводится.\n{tail}")
        return 0
    print(
        f"ВНИМАНИЕ: тест проходит на {args.ref} — он не воспроизводит исправленный дефект.\n{tail}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
