#!/usr/bin/env python3
"""Миграции согласованы с моделями: upgrade head → alembic check → downgrade base → upgrade head.

Запускается на временной SQLite-базе (без сети и Docker). На PostgreSQL миграции проверяют
интеграционные тесты. Файл защищён.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def alembic(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--locked", "alembic", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{Path(tmp) / 'check.db'}"}
        for label, args in (
            ("upgrade head", ["upgrade", "head"]),
            ("модели = миграции", ["check"]),
            ("downgrade base", ["downgrade", "base"]),
            ("повторный upgrade head", ["upgrade", "head"]),
        ):
            proc = alembic(*args, env=env)
            if proc.returncode != 0:
                tail = (proc.stdout + proc.stderr).strip()[-1500:]
                print(f"migrations: FAIL на шаге «{label}»:\n{tail}")
                if label == "модели = миграции":
                    print('Схема в коде расходится с миграциями: just db-revision "описание"')
                return 1
    print("migrations: ok (upgrade, check, downgrade, upgrade)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
