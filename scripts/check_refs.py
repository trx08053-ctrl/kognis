#!/usr/bin/env python3
"""Актуальность ссылок документации на код.

Проверяет в AGENTS.md, README.md, docs/**/*.md (кроме docs/templates и плана docs/HARNESS.md):
- `path/to/file.py::symbol` (или `Class.method`) — файл есть и символ в нём определён;
- `src/...`, `tests/...`, `scripts/...`, `docs/...` в обратных кавычках — путь существует;
- при наличии docs/modules/: у каждого компонента корневого пакета есть карточка и нет
  карточек для удалённых компонентов.
- ADR с разделом «## Исключение» содержит заполненные Причину, Ответственного и Пересмотр.
Шаблоны с <...>, *, {...} не проверяются. Файл защищён.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYMBOL_REF = re.compile(r"`([\w./-]+\.py)::([\w.]+)`")
PATH_REF = re.compile(r"`((?:src|tests|scripts|docs)/[^`\s]+?)(?::\d+)?`")
PLACEHOLDER = re.compile(r"[<>*{}]")


def doc_files() -> list[Path]:
    files = [ROOT / n for n in ("AGENTS.md", "README.md", "CLAUDE.md") if (ROOT / n).exists()]
    # HARNESS.md — план процесса, описывает целевую структуру, а не текущий код
    files += [
        p
        for p in sorted((ROOT / "docs").rglob("*.md"))
        if "templates" not in p.parts and p.name != "HARNESS.md"
    ]
    return files


def symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                    names.add(f"{node.name}.{item.name}")
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


EXCEPTION_FIELDS = ("Причина", "Ответственный", "Пересмотр")


def exception_errors() -> list[str]:
    """Временное архитектурное исключение без причины, ответственного или условия пересмотра."""
    errors: list[str] = []
    for adr in sorted((ROOT / "docs" / "adr").glob("*.md")):
        text = re.sub(r"<!--.*?-->", "", adr.read_text(), flags=re.S)
        if "## Исключение" not in text:
            continue
        section = text.split("## Исключение", 1)[1].split("\n## ", 1)[0]
        for name in EXCEPTION_FIELDS:
            match = re.search(rf"\*\*{name}:\*\*\s*(.+)", section)
            if not match or match.group(1).strip() in {"", "…", "..."}:
                errors.append(f"docs/adr/{adr.name}: исключение без поля «{name}»")
    return errors


def components() -> set[str] | None:
    src = ROOT / "src"
    packages = [p for p in src.iterdir() if (p / "__init__.py").exists()] if src.exists() else []
    if len(packages) != 1:
        return None
    result: set[str] = set()
    for child in packages[0].iterdir():
        if child.name.startswith(("_", ".")):
            continue
        if child.is_dir() and (child / "__init__.py").exists():
            result.add(child.name)
        elif child.suffix == ".py":
            result.add(child.stem)
    return result


def main() -> int:
    errors: list[str] = []
    for doc in doc_files():
        text = doc.read_text()
        where = doc.relative_to(ROOT).as_posix()
        for match in SYMBOL_REF.finditer(text):
            file, symbol = match.groups()
            if PLACEHOLDER.search(file):
                continue
            path = ROOT / file
            if not path.exists():
                errors.append(f"{where}: `{file}::{symbol}` — файла нет")
            elif symbol not in symbols(path):
                errors.append(f"{where}: `{file}::{symbol}` — символ не найден")
        for match in PATH_REF.finditer(text):
            ref = match.group(1).split("::")[0].rstrip("/.,")
            if PLACEHOLDER.search(ref) or ref.startswith("docs/generated"):
                continue
            if not (ROOT / ref).exists():
                errors.append(f"{where}: `{ref}` — путь не существует")

    cards_dir = ROOT / "docs" / "modules"
    comps = components()
    if cards_dir.exists() and comps is not None:
        cards = {p.stem for p in cards_dir.glob("*.md")}
        errors += [
            f"docs/modules/{c}.md — нет карточки компонента (just module-card {c})"
            for c in sorted(comps - cards)
        ]
        errors += [
            f"docs/modules/{c}.md — карточка для несуществующего компонента"
            for c in sorted(cards - comps)
        ]

    errors += exception_errors()
    if errors:
        print("Устаревшие ссылки документации на код:")
        print("\n".join(f"  {e}" for e in errors))
        return 1
    print("refs: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
