#!/usr/bin/env python3
"""ARCHITECTURE.md не расходится с кодом (раздел «3. Модули»). Файл защищён.

Сверяет таблицу модулей и диаграмму mermaid с фактами из кода:
- строка есть у каждого модуля из src/<pkg>/, нет строк у несуществующих (кроме «(план)»);
- «(план)» у модуля, у которого уже есть публичный API (`__all__` не пуст), — ошибка;
- каждая таблица БД (`Table("имя", …)`) указана в «Владеет данными» своего модуля и только его;
- реальные импорты между модулями входят в «Может использовать» («все» — любой модуль);
- стрелки диаграммы есть в коде; связи бизнес-модулей (с `_domain.py`) есть на диаграмме;
- у каждого риска раздела 8 — записанный результат или ОТКРЫТАЯ задача bd (иначе риск теряется);
- у каждого пункта docs/TECH_DEBT.md — открытая задача bd или «пересмотр ГГГГ-ММ-ДД» в будущем;
- каждая переменная окружения из кода (os.environ / getenv) описана в README или RUNBOOK.
"""

from __future__ import annotations

import ast
import datetime as dt
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "ARCHITECTURE.md"
TICKS = re.compile(r"`([A-Za-z_][\w.]*)`")
COLUMNS = 5  # Модуль | Ответственность | Владеет данными | Публичный API | Может использовать


def package() -> Path | None:
    pkgs = [p for p in (ROOT / "src").glob("*") if (p / "__init__.py").exists()]
    return pkgs[0] if len(pkgs) == 1 else None


def code_facts(pkg: Path) -> tuple[dict[str, set[str]], dict[str, str], set[str], set[str]]:
    """Зависимости модулей, владельцы таблиц, модули с публичным API, бизнес-модули."""
    modules = [p for p in pkg.iterdir() if (p / "__init__.py").exists()]
    names = {p.name for p in modules}
    deps: dict[str, set[str]] = {n: set() for n in names}
    tables: dict[str, str] = {}
    public: set[str] = set()
    for mod in modules:
        for path in mod.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if parts[0] == pkg.name and len(parts) > 1 and parts[1] in names:
                        deps[mod.name].add(parts[1])
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "Table"
                    and node.args
                    and isinstance(first := node.args[0], ast.Constant)
                ):
                    tables[str(first.value)] = mod.name
                if (
                    isinstance(node, ast.Assign)
                    and path.name == "__init__.py"
                    and isinstance(target := node.targets[0], ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.List | ast.Tuple)
                    and node.value.elts
                ):
                    public.add(mod.name)
        deps[mod.name].discard(mod.name)
    business = {p.name for p in modules if (p / "_domain.py").exists()}
    return deps, tables, public, business


def parse_doc(text: str) -> tuple[dict[str, list[str]], set[tuple[str, str]]]:
    section = re.search(r"^## 3\..*?(?=^## 4\.|\Z)", text, re.M | re.S)
    body = section.group(0) if section else ""
    rows: dict[str, list[str]] = {}
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) < COLUMNS or set(cells[0]) <= {"-", " "}:
            continue
        match = re.match(r"\[?`?([a-z_][a-z0-9_]*)`?\]?", cells[0])
        if match and cells[0] != "Модуль":
            rows[match.group(1)] = cells
    edges: set[tuple[str, str]] = set()
    for block in re.findall(r"```mermaid\n(.*?)```", body, re.S):
        for line in block.splitlines():
            chain = [n.strip() for n in re.split(r"-->|---", line) if n.strip()]
            if len(chain) > 1:
                chain = [re.split(r"[\[(\s]", n)[0] for n in chain]
                edges |= set(itertools.pairwise(chain))
    return rows, edges


def check_rows(
    rows: dict[str, list[str]], deps: dict[str, set[str]], public: set[str]
) -> list[str]:
    errors = [f"модуля `{m}` нет в таблице модулей" for m in sorted(set(deps) - set(rows))]
    for mod, cells in rows.items():
        planned = "план" in cells[0]
        if mod not in deps and not planned:
            errors.append(f"строка `{mod}`: такого модуля нет в коде (или пометьте «(план)»)")
        if planned and mod in public:
            errors.append(f"`{mod}` помечен «(план)», но уже реализован (есть публичный API)")
    for mod, used in sorted(deps.items()):
        cells = rows.get(mod)
        if (
            cells
            and "все" not in cells[4]
            and (extra := sorted(used - set(TICKS.findall(cells[4]))))
        ):
            errors.append(f"`{mod}` использует {extra}, а в «Может использовать» этого нет")
    return errors


def check_tables(rows: dict[str, list[str]], tables: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for table, owner in sorted(tables.items()):
        listed = [m for m, cells in rows.items() if table in TICKS.findall(cells[2])]
        if owner in rows and owner not in listed:
            errors.append(f"таблица `{table}` (владелец по коду — `{owner}`) не указана у него")
        errors += [
            f"таблица `{table}` указана у `{m}`, а владеет ею `{owner}`"
            for m in listed
            if m != owner
        ]
    return errors


def check_diagram(
    edges: set[tuple[str, str]], deps: dict[str, set[str]], business: set[str]
) -> list[str]:
    errors = [
        f"на диаграмме `{a} --> {b}`, но `{a}` не импортирует `{b}`"
        for a, b in sorted(edges)
        if a in deps and b in deps and b not in deps[a]
    ]
    errors += [
        f"на диаграмме нет связи `{a} --> {b}` (она есть в коде)"
        for a in sorted(business)
        for b in sorted(deps[a] & business)
        if (a, b) not in edges
    ]
    return errors


NO_RESULT = re.compile(r"^(|—|-|…|\.\.\.|вынесен.*|см\. задачу.*|todo|позже)$", re.I)


def task_status(task_id: str) -> str:
    """Статус задачи: из bd, а без базы bd (CI, свежий клон) — из экспорта .beads/issues.jsonl."""
    out = subprocess.run(["bd", "show", task_id, "--json"], cwd=ROOT, capture_output=True,
                         text=True, check=False).stdout  # fmt: skip
    try:
        data: object = json.loads(out or "{}")
    except ValueError:
        data = {}
    items = cast("list[object]", data) if isinstance(data, list) else [data]
    item: object = items[0] if items else None
    if isinstance(item, dict):
        fields = cast("dict[str, object]", item)
        if fields.get("id") == task_id:
            return str(fields.get("status", ""))
    export = ROOT / ".beads" / "issues.jsonl"
    for line in export.read_text().splitlines() if export.exists() else []:
        row = cast("dict[str, object]", json.loads(line)) if line.strip() else {}
        if row.get("id") == task_id:
            return str(row.get("status", ""))
    return ""


def check_risks(text: str) -> list[str]:
    section = re.search(r"^## 8\..*?(?=^## |\Z)", text, re.M | re.S)
    errors: list[str] = []
    for line in (section.group(0) if section else "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not re.fullmatch(r"R\d+", cells[0] if cells else ""):
            continue
        result, tasks = cells[-1], re.findall(r"\b[a-z][a-z0-9-]*-[a-z0-9]{3}\b", line)
        open_tasks = [t for t in tasks if task_status(t) not in {"", "closed"}]
        if NO_RESULT.match(result) and not open_tasks:
            errors.append(
                f"{cells[0]}: нет результата и нет открытой задачи — запишите итог "
                "(подтверждено/опровергнуто, данными) или заведите задачу bd и укажите её id"
            )
    return errors


TASK_ID = re.compile(r"\b[a-z][a-z0-9-]*-[a-z0-9]{3}\b")
REVIEW_DATE = re.compile(r"пересмотр[:\s]*(\d{4}-\d{2}-\d{2})", re.I)
ENV_READ = re.compile(r"""(?:environ\.get\(|getenv\(|environ\[)\s*["']([A-Z][A-Z0-9_]+)["']""")


def check_debt() -> list[str]:
    path = ROOT / "docs" / "TECH_DEBT.md"
    errors: list[str] = []
    for line in path.read_text().splitlines() if path.exists() else []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or not re.fullmatch(r"TD-\d+", cells[0]):
            continue
        open_tasks = [t for t in TASK_ID.findall(line) if task_status(t) not in {"", "closed"}]
        dates = [dt.date.fromisoformat(d) for d in REVIEW_DATE.findall(line)]
        if not open_tasks and not any(d >= dt.date.today() for d in dates):
            errors.append(
                f"TECH_DEBT {cells[0]}: нет открытой задачи bd и даты «пересмотр ГГГГ-ММ-ДД» — "
                "заведите задачу, назначьте пересмотр или удалите пункт, если долг погашен"
            )
    return errors


def check_config() -> list[str]:
    docs = " ".join(
        p.read_text() for p in (ROOT / "README.md", ROOT / "docs" / "RUNBOOK.md") if p.exists()
    )
    names = sorted(
        {n for f in (ROOT / "src").rglob("*.py") for n in ENV_READ.findall(f.read_text())}
    )
    return [
        f"переменная окружения {n} читается в коде, но не описана в README.md или docs/RUNBOOK.md"
        for n in names
        if not re.search(rf"\b{n}\b", docs)
    ]


def main() -> int:
    pkg = package()
    if pkg is None or not DOC.exists():
        return 0
    deps, tables, public, business = code_facts(pkg)
    rows, edges = parse_doc(DOC.read_text())
    errors = check_rows(rows, deps, public) + check_tables(rows, tables)
    errors += check_diagram(edges, deps, business)
    errors += check_risks(DOC.read_text()) + check_debt() + check_config()
    if errors:
        print("Документация расходится с кодом (ARCHITECTURE, TECH_DEBT, настройки):")
        print("\n".join(f"  - {e}" for e in errors))
        print("Обнови таблицу и диаграмму по коду (`just map`, `just context <модуль>`).")
        return 1
    print(f"arch-doc: ok ({len(rows)} модулей, {len(tables)} таблиц)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
