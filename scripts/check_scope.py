#!/usr/bin/env python3
"""Сверка заявленной области влияния задачи с фактическими изменениями — сигналы для ревью.

    check_scope.py <task-id>

Изменения = коммиты с `<task-id>` в сообщении + незакоммиченное. Сигналы, не ошибки:
незаявленный модуль; публичный API / контракт / данные / .importlinter при «нет» в TASK;
число файлов — для диагностики. Объяснение — в PROGRESS.md или обновлённом разделе 2a. Файл защищён.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_MODULE = 2  # src/<pkg>/<модуль>/…
DATA_PATHS = re.compile(r"(^|/)(migrations|alembic)/|schema", re.I)


def git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return [line for line in out.stdout.splitlines() if line.strip()]


def field(text: str, label: str) -> str:
    match = re.search(rf"^- \*\*{label}:\*\*(.*)$", text, re.M)
    return match.group(1).strip() if match else ""


def evolution_signals(text: str, changed: set[str], says_no: Callable[[str], bool]) -> list[str]:
    """Изменения данных: заполнен ли раздел 2b и есть ли тест миграции на данных прошлой версии."""
    signals: list[str] = []
    data_declared = field(text, "Данные") and not says_no("Данные")
    evolution = text.split("## 2b.", 1)[1].split("\n## ", 1)[0] if "## 2b." in text else ""
    if data_declared and (not evolution or "было → стало" in evolution):
        signals.append("в 2a заявлены изменения данных, а раздел 2b (эволюция) не заполнен")
    migration_changed = any(DATA_PATHS.search(f) for f in changed)
    migration_test = any(
        f.startswith("tests/") and "pytest.mark.migration" in (ROOT / f).read_text()
        for f in changed
        if f.endswith(".py") and (ROOT / f).exists()
    )
    if migration_changed and not migration_test:
        signals.append(
            "миграция изменена без теста @pytest.mark.migration на данных прошлой версии"
        )
    return signals


def main() -> int:
    task_id = sys.argv[1] if len(sys.argv) > 1 else ""
    task_md = ROOT / "tasks" / task_id / "TASK.md"
    if not task_md.exists():
        sys.exit(f"нет {task_md.relative_to(ROOT)}")
    text = task_md.read_text()
    changed = set(git("log", f"--grep={task_id}", "--name-only", "--format="))
    changed |= set(git("diff", "--name-only", "HEAD"))
    changed |= set(git("ls-files", "--others", "--exclude-standard"))
    changed = {f for f in changed if not f.startswith(("tasks/", ".beads/", "docs/MAP.md"))}
    packages = [p for p in (ROOT / "src").iterdir() if (p / "__init__.py").exists()]
    pkg = packages[0].name if len(packages) == 1 else ""
    modules: set[str] = set()
    if pkg:
        modules = {p.name for p in (ROOT / "src" / pkg).iterdir() if p.is_dir()}
    touched: set[str] = set()
    for f in changed:
        parts = f.split("/")
        if parts[0] == "src" and len(parts) > SRC_MODULE and parts[SRC_MODULE] in modules:
            touched.add(parts[SRC_MODULE])
        elif parts[0] == "tests" and len(parts) > 1 and parts[1] in modules:
            touched.add(parts[1])
    declared_line = field(text, "Модули")
    declared = {m for m in modules if re.search(rf"\b{re.escape(m)}\b", declared_line)}

    def says_no(label: str) -> bool:
        return bool(re.match(r"(нет|—|-|no)\b", field(text, label), re.I))

    signals: list[str] = []
    signals += [f"изменён модуль `{m}`, не заявленный в 2a — объясните или обновите TASK"
                for m in sorted(touched - declared)]  # fmt: skip
    api = sorted(m for m in touched if f"src/{pkg}/{m}/__init__.py" in changed)
    if api and says_no("Публичные интерфейсы"):
        signals.append(f"изменён публичный API {api}, а в TASK «нет» — нужен процесс согласования")
    if any(f.startswith("docs/contracts/") for f in changed) and says_no("Публичные интерфейсы"):
        signals.append(
            "изменён контракт в docs/contracts/, а в TASK «нет» — согласование с человеком"
        )
    if any(DATA_PATHS.search(f) for f in changed) and says_no("Данные"):
        signals.append("изменения схемы/миграций, а в TASK «Данные: нет» — см. docs/EVOLUTION.md")
    signals += evolution_signals(text, changed, says_no)
    if ".importlinter" in changed:
        signals.append(".importlinter изменён — требуется ADR и решение человека")

    print(f"Область задачи {task_id}: заявлено {sorted(declared) or '—'}, "
          f"затронуто {sorted(touched) or '—'}, файлов {len(changed)} (диагностика)")  # fmt: skip
    for m in sorted(declared - touched):
        print(f"  info: заявлен `{m}`, но не изменён")
    for s in signals:
        print(f"  ⚠ {s}")
    if not signals:
        print("  расхождений нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
