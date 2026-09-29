#!/usr/bin/env python3
"""Проверки безопасности: код (SAST) и зависимости. Файл защищён.

    check_security.py sast      Semgrep: правила harness (security/semgrep.yml), проекта
                                (security/project.yml, если есть) и наборы OWASP из реестра Semgrep
    check_security.py deps      osv-scanner по uv.lock и frontend/pnpm-lock.yaml
    check_security.py update    обновить наборы правил и базы уязвимостей (нужна сеть)

Ruff (правила S) и Biome (security) работают в lint/frontend; здесь — то, чего они не видят.
Правила и базы кэшируются в ~/.cache (проверка работает без сети, в том числе в песочнице агента).
Подавление — комментарий nosemgrep с `justified: <task-id> <причина>` (no-weakening, ratchet).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMGREP = ["uvx", "-q", "--from", "semgrep==1.177.0", "semgrep"]
PACKS = ["owasp-top-ten", "python", "javascript", "react", "jwt"]
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
PACK_DIR = CACHE / "dev-harness" / "semgrep"
TARGETS = ["src", "frontend/src"]
LOCKFILES = ["uv.lock", "frontend/pnpm-lock.yaml"]
FRESH_S = 7 * 24 * 3600
STAMP = PACK_DIR / ".updated"


def update() -> int:
    """Обновить кэш правил и баз; свежий (< 7 дней) не трогать, если не передан --force."""
    fresh = STAMP.exists() and time.time() - STAMP.stat().st_mtime < FRESH_S
    if fresh and "--force" not in sys.argv:
        print(f"правила и базы свежие ({PACK_DIR}); принудительно: update --force")
        return 0
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    for pack in PACKS:
        url = f"https://semgrep.dev/c/p/{pack}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            (PACK_DIR / f"{pack}.yml").write_bytes(resp.read())
        print(f"правила {pack}: обновлены")
    locks = [a for f in LOCKFILES if (ROOT / f).exists() for a in ("--lockfile", f)]
    subprocess.run(
        ["osv-scanner", "scan", "source", "--offline-vulnerabilities",
         "--download-offline-databases", *locks],
        cwd=ROOT, capture_output=True, check=False,
    )  # fmt: skip
    print("база уязвимостей osv: обновлена")
    STAMP.touch()
    return 0


def sast() -> int:
    missing = [p for p in PACKS if not (PACK_DIR / f"{p}.yml").exists()]
    if missing:
        print(f"нет наборов правил {missing} в {PACK_DIR} — `just security-update` (нужна сеть)")
        return 1
    configs = [ROOT / "security" / "semgrep.yml", ROOT / "security" / "project.yml"]
    configs += [PACK_DIR / f"{p}.yml" for p in PACKS]
    args = [a for c in configs if c.exists() for a in ("--config", str(c))]
    targets = [t for t in TARGETS if (ROOT / t).exists()]
    proc = subprocess.run(
        [*SEMGREP, "scan", "--metrics=off", "--disable-version-check", "--json", *args, *targets],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"semgrep не выполнился:\n{proc.stderr.strip()[-1500:]}")
        return 1
    errors = [e for e in report.get("errors", []) if e.get("level") == "error"]
    for err in errors:
        print(f"ошибка semgrep: {str(err.get('message', ''))[:300]}")
    results = report.get("results", [])
    for r in results:
        rule = str(r["check_id"]).split(".")[-1]
        message = " ".join(str(r["extra"].get("message", "")).split())[:240]
        print(f"{r['path']}:{r['start']['line']}: [{rule}] {message}")
    if results:
        print(
            f"\nSAST: {len(results)} находок. Исправьте код; ложное срабатывание — комментарий "
            "nosemgrep: <id> с `justified: <task-id> <причина>` (решение видит ревью)."
        )
    else:
        print(f"SAST: ok ({len(configs)} наборов правил, {', '.join(targets)})")
    return 1 if results or errors else 0


def deps() -> int:
    if shutil.which("osv-scanner") is None:
        print("нет osv-scanner — mise install")
        return 1
    locks = [a for f in LOCKFILES if (ROOT / f).exists() for a in ("--lockfile", f)]
    proc = subprocess.run(
        ["osv-scanner", "scan", "source", "--offline-vulnerabilities", *locks],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    out = (proc.stdout + proc.stderr).strip()
    if "local db" not in out and proc.returncode != 0:
        print(f"нет локальной базы уязвимостей — выполните `just security-update`\n{out[-800:]}")
        return 1
    if proc.returncode != 0:
        print(out[-4000:])
        print(
            "\nDEPS: известные уязвимости — обновите пакет до исправленной версии (решает человек)."
        )
        return 1
    print("DEPS: ok (известных уязвимостей нет)")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    actions = {"sast": sast, "deps": deps, "update": update}
    if command not in actions:
        print(__doc__)
        return 2
    return actions[command]()


if __name__ == "__main__":
    sys.exit(main())
