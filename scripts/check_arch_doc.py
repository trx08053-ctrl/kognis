#!/usr/bin/env python3
"""ARCHITECTURE.md не расходится с кодом (раздел «3. Модули»). Файл защищён.

Сверяет таблицу модулей и диаграмму mermaid с фактами из кода:
- строка есть у каждого модуля из src/<pkg>/, нет строк у несуществующих (кроме «(план)»);
- «(план)» у модуля, у которого уже есть публичный API (`__all__` не пуст), — ошибка;
- каждая таблица БД (`Table("имя", …)`) указана в «Владеет данными» своего модуля и только его;
- реальные импорты между модулями входят в «Может использовать» («все» — любой модуль);
- стрелки диаграммы есть в коде; связи бизнес-модулей (с `_domain.py`) есть на диаграмме.
"""

from __future__ import annotations

import ast
import itertools
import re
import sys
from pathlib import Path

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


def main() -> int:
    pkg = package()
    if pkg is None or not DOC.exists():
        return 0
    deps, tables, public, business = code_facts(pkg)
    rows, edges = parse_doc(DOC.read_text())
    errors = check_rows(rows, deps, public) + check_tables(rows, tables)
    errors += check_diagram(edges, deps, business)
    if errors:
        print("docs/ARCHITECTURE.md расходится с кодом (раздел «3. Модули»):")
        print("\n".join(f"  - {e}" for e in errors))
        print("Обнови таблицу и диаграмму по коду (`just map`, `just context <модуль>`).")
        return 1
    print(f"arch-doc: ok ({len(rows)} модулей, {len(tables)} таблиц)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
