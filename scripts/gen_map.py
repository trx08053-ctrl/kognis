#!/usr/bin/env python3
"""Карта проекта docs/MAP.md, извлечённая из кода (Python ast, без импорта модулей).

    gen_map.py           перегенерировать docs/MAP.md
    gen_map.py --check   exit 1, если MAP.md не совпадает с кодом (устарел)

Компонент = подпакет или модуль первого уровня корневого пакета (src/<pkg>/<component>).
Для каждого: назначение (первая строка docstring), публичный интерфейс (__all__ → файл определения),
зависимости от других компонентов, тесты, импортирующие компонент, карточка docs/modules/<name>.md.
Файл защищён.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
MAP = ROOT / "docs" / "MAP.md"
CARDS = ROOT / "docs" / "modules"
MAX_REEXPORT_DEPTH = 5


@dataclass
class Component:
    name: str
    path: Path
    doc: str = ""
    public: list[tuple[str, str]] = field(default_factory=list)  # (имя, файл)
    deps: set[str] = field(default_factory=set)
    tests: set[str] = field(default_factory=set)
    files: int = 0


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def root_package() -> Path:
    packages = sorted(p for p in SRC.iterdir() if (p / "__init__.py").exists())
    if len(packages) != 1:
        sys.exit(f"ожидался один пакет в src/, найдено: {[p.name for p in packages]}")
    return packages[0]


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def first_doc_line(tree: ast.Module) -> str:
    doc = ast.get_docstring(tree) or ""
    return doc.strip().splitlines()[0] if doc.strip() else ""


def module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(tree: ast.Module, current: str, is_package: bool) -> set[str]:
    """Абсолютные имена импортируемых модулей (относительные импорты разрешаются)."""
    result: set[str] = set()
    base = current.split(".") if is_package else current.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = base[: len(base) - node.level + 1]
                mod = ".".join([*anchor, node.module] if node.module else anchor)
            else:
                mod = node.module or ""
            result.add(mod)
            result.update(f"{mod}.{alias.name}" for alias in node.names)
    return result


def definitions(tree: ast.Module) -> dict[str, int]:
    names: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names[target.id] = node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names[node.target.id] = node.lineno
    return names


def declared_all(tree: ast.Module) -> list[str] | None:
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant)
                    and isinstance(e.value, str)]  # fmt: skip
    return None


def locate(name: str, module: str, seen: int = 0) -> str | None:
    """Где определено имя, экспортируемое модулем (идём по цепочке from-импортов)."""
    path = module_path(module)
    if path is None or seen > MAX_REEXPORT_DEPTH:
        return None
    tree = parse(path)
    defs = definitions(tree)
    if name in defs:
        return rel(path)  # без номера строки: строки даёт LSP, а карта не устаревает от сдвигов
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and any(
            (a.asname or a.name) == name for a in node.names
        ):
            base = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
            anchor = base[: len(base) - node.level + 1] if node.level else []
            target = ".".join([*anchor, node.module] if node.module else anchor)
            original = next(a.name for a in node.names if (a.asname or a.name) == name)
            return locate(original, target, seen + 1) or locate(
                original, f"{target}.{original}", seen + 1
            )
    return None


def module_path(module: str) -> Path | None:
    base = SRC.joinpath(*module.split("."))
    for candidate in (base / "__init__.py", base.with_suffix(".py")):
        if candidate.exists():
            return candidate
    return None


def discover(package: Path) -> dict[str, Component]:
    components: dict[str, Component] = {}
    for child in sorted(package.iterdir()):
        if child.name.startswith(("_", ".")) or child.name == "py.typed":
            continue
        if child.is_dir() and (child / "__init__.py").exists():
            components[child.name] = Component(child.name, child)
        elif child.suffix == ".py":
            components[child.stem] = Component(child.stem, child)
    return components


def analyze(comp: Component, pkg: str, components: dict[str, Component]) -> None:
    """Назначение, публичный интерфейс, размер и зависимости компонента."""
    files = sorted(comp.path.rglob("*.py")) if comp.path.is_dir() else [comp.path]
    entry = comp.path / "__init__.py" if comp.path.is_dir() else comp.path
    tree = parse(entry)
    comp.doc = first_doc_line(tree)
    module = f"{pkg}.{comp.name}"
    exported = declared_all(tree)
    if exported is None:
        exported = sorted(n for n in definitions(tree) if not n.startswith("_"))
    comp.public = [(n, locate(n, module) or "?") for n in exported]
    for file in files:
        comp.files += 1
        file_tree = parse(file)
        for imp in imported_modules(file_tree, module_name(file), file.name == "__init__.py"):
            parts = [*imp.split("."), ""]
            if parts[0] == pkg and parts[1] in components and parts[1] != comp.name:
                comp.deps.add(parts[1])


def collect() -> tuple[str, list[Component]]:
    package = root_package()
    pkg = package.name
    components = discover(package)
    for comp in components.values():
        analyze(comp, pkg, components)
    for test in sorted((ROOT / "tests").rglob("test_*.py")):
        imports = imported_modules(parse(test), "tests.x", is_package=False)
        for comp in components.values():
            module = f"{pkg}.{comp.name}"
            names = {n for n, _ in comp.public}
            if any(i == module or i.startswith(module + ".") for i in imports) or any(
                i.startswith(f"{pkg}.") and i.split(".")[-1] in names for i in imports
            ):
                comp.tests.add(rel(test))
    return pkg, list(components.values())


def entry_points() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    scripts: dict[str, str] = data.get("project", {}).get("scripts", {})
    return [f"`{name}` → `{target}`" for name, target in sorted(scripts.items())]


def render() -> str:
    pkg, components = collect()
    out = [
        "# Карта проекта",
        "",
        "> Генерируется `just map` из кода — не редактировать вручную. `just check map` проверяет",
        "> актуальность. Архитектурные правила — [ARCHITECTURE.md](ARCHITECTURE.md),",
        "> границы — `.importlinter`.",
        "",
        f"Корневой пакет: `{pkg}` · компонентов: {len(components)}",
        "",
        "## Компоненты",
        "",
        "| Компонент | Назначение | Зависит от | Файлов | Карточка |",
        "|---|---|---|---|---|",
    ]
    for c in components:
        card = CARDS / f"{c.name}.md"
        card_link = f"[{c.name}](modules/{c.name}.md)" if card.exists() else "**нет**"
        deps = ", ".join(f"`{d}`" for d in sorted(c.deps)) or "—"
        out.append(f"| `{pkg}.{c.name}` | {c.doc or '—'} | {deps} | {c.files} | {card_link} |")
    for c in components:
        out += ["", f"## `{pkg}.{c.name}`", "", f"- Код: `{rel(c.path)}`"]
        if c.public:
            out.append("- Публичный интерфейс:")
            out += [f"  - `{name}` — `{where}`" for name, where in c.public]
        else:
            out.append("- Публичный интерфейс: —")
        out.append("- Тесты: " + (", ".join(f"`{t}`" for t in sorted(c.tests)) or "**нет**"))
    points = entry_points()
    out += ["", "## Точки входа", "", *(f"- {p}" for p in points)] if points else []
    return "\n".join(out) + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not MAP.exists() or MAP.read_text() != content:
            print("docs/MAP.md устарел относительно кода — выполните `just map` и закоммитьте.")
            return 1
        print("map: ok")
        return 0
    MAP.parent.mkdir(exist_ok=True)
    MAP.write_text(content)
    print(f"записано: {rel(MAP)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
