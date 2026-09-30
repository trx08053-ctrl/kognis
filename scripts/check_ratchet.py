#!/usr/bin/env python3
"""Храповик качества: показатели могут только улучшаться.

    check_ratchet.py            проверка (после тестов: нужен coverage.xml)
    check_ratchet.py --update   поднять планку до текущих значений (только в лучшую сторону)

Правила:
- общее покрытие строк ≥ зафиксированного в .quality-baseline.json;
- покрытие изменённых строк (diff-cover против main или HEAD) ≥ DIFF_FLOOR %;
- новые подавления с пометкой `justified:` запрещены поштучно (список в планке; подмена одного
  другим тоже ловится); удалённые — просто исчезают из планки при ratchet-up.
Понизить планку можно только правкой .quality-baseline.json — это защищённый файл, решение человека.
Файл защищён.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_i18n

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".quality-baseline.json"
COVERAGE_XML = ROOT / "coverage.xml"
DIFF_FLOOR = 80
CODE_DIRS = ("src", "tests", "frontend/src")  # код проекта; скрипты harness защищены отдельно
CODE_SUFFIXES = {".py", ".ts", ".tsx"}
JUSTIFIED = re.compile(r"justified:\s*[\w.-]+-\w+")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def coverage() -> float:
    if not COVERAGE_XML.exists():
        sys.exit("нет coverage.xml — сначала тесты (just check tests ratchet)")
    rate = ET.parse(COVERAGE_XML).getroot().get("line-rate", "0")  # noqa: S314  justified: harness-cov own pytest-cov output
    return round(float(rate) * 100, 2)


def suppressions() -> list[str]:
    """Подавления как `путь: строка` (без номера строки — сдвиги кода не считаются изменением)."""
    found: list[str] = []
    for folder in CODE_DIRS:
        paths = list((ROOT / folder).rglob("*")) if (ROOT / folder).is_dir() else list[Path]()
        for path in sorted(p for p in paths if p.suffix in CODE_SUFFIXES):
            rel = path.relative_to(ROOT).as_posix()
            found += [f"{rel}: {ln.strip()}" for ln in path.read_text().splitlines()
                      if JUSTIFIED.search(ln)]  # fmt: skip
    return sorted(found)


def compare_ref() -> str:
    for ref in ("origin/main", "main"):
        if (
            git("rev-parse", "--verify", "--quiet", ref)
            and git("branch", "--show-current") != "main"
        ):
            return git("merge-base", "HEAD", ref) or "HEAD"
    return "HEAD"


def diff_coverage() -> tuple[bool, str]:
    proc = subprocess.run(
        ["uv", "run", "--locked", "diff-cover", str(COVERAGE_XML),
         f"--compare-branch={compare_ref()}", f"--fail-under={DIFF_FLOOR}"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    summary = [
        line
        for line in proc.stdout.splitlines()
        if line.startswith(("Total:", "Missing:", "Coverage:", "No lines"))
    ]
    return proc.returncode == 0, "; ".join(summary) or proc.stdout.strip()[-300:]


def load() -> tuple[float, list[str] | None]:
    """(планка покрытия, разрешённые подавления); None — планки подавлений ещё нет."""
    try:
        data = json.loads(BASELINE.read_text())
    except (OSError, ValueError):
        return 0.0, None
    raw = data.get("suppressions")
    allowed: list[str] | None
    if isinstance(raw, list):
        allowed = [str(x) for x in cast("list[object]", raw)]
    else:  # старый формат (число): без поштучного списка разрешено только 0
        allowed = [] if raw == 0 else None
    return float(data.get("coverage", 0.0)), allowed


FRONT_SUMMARY = ROOT / "frontend" / "coverage" / "coverage-summary.json"


def frontend_coverage() -> dict[str, float]:
    """Покрытие фронтенда (vitest --coverage, json-summary): {lines, branches} или пусто."""
    if not FRONT_SUMMARY.exists():
        return {}
    total = json.loads(FRONT_SUMMARY.read_text()).get("total", {})
    return {k: float(total[k]["pct"]) for k in ("lines", "branches") if k in total}


def main() -> int:
    base_cov, allowed = load()
    cov, supp = coverage(), suppressions()
    stored = cast("dict[str, Any]", json.loads(BASELINE.read_text()) if BASELINE.exists() else {})
    front_base = cast("dict[str, float]", stored.get("frontend_coverage") or {})
    base_front = {k: float(v) for k, v in front_base.items()}
    front = frontend_coverage()
    if "--update" in sys.argv:
        kept = supp if allowed is None else [s for s in supp if s in allowed]
        # прочие планки (например i18n_hardcoded) сохраняются: их владельцы — свои проверки
        new: dict[str, object] = {**stored, "coverage": max(cov, base_cov), "suppressions": kept}
        debt = stored.get(check_i18n.KEY)
        if isinstance(debt, list):
            new[check_i18n.KEY] = check_i18n.shrink([str(x) for x in cast("list[object]", debt)])
        if front or base_front:
            new["frontend_coverage"] = {
                k: max(front.get(k, 0.0), base_front.get(k, 0.0)) for k in {*front, *base_front}
            }
        BASELINE.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
        print(f"планка: покрытие {new['coverage']}%, подавлений {len(kept)}")
        return 0

    errors: list[str] = []
    if cov + 0.01 < base_cov:
        errors.append(f"покрытие упало: {cov}% < планки {base_cov}%")
    new_supp = [s for s in supp if allowed is not None and s not in allowed]
    if new_supp:
        errors.append(
            "новые подавления (исправьте код или согласуйте с человеком — он добавит их в "
            ".quality-baseline.json):\n    " + "\n    ".join(new_supp)
        )
    errors += [
        f"покрытие фронтенда ({k}) упало: {front[k]}% < планки {v}%"
        for k, v in base_front.items()
        if k in front and front[k] + 0.01 < v
    ]
    diff_ok, diff_info = diff_coverage()
    if not diff_ok:
        errors.append(f"покрытие изменённых строк < {DIFF_FLOOR}%: {diff_info}")

    print(f"покрытие {cov}% (планка {base_cov}%), подавлений {len(supp)}, diff: {diff_info}")
    if errors:
        print("RATCHET FAIL:\n" + "\n".join(f"  {e}" for e in errors))
        return 1
    if cov > base_cov + 0.5 or (allowed is not None and len(supp) < len(allowed)):
        print("показатели лучше планки — зафиксируйте: just ratchet-up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
