#!/usr/bin/env python3
"""Границы бизнес-модулей: только публичный API и без циклов.

Модуль — подпакет корневого пакета (`src/<pkg>/<модуль>/`). Его публичный API — `__init__.py`
(`__all__`); всё с `_` в имени — внутренности. Ошибка, если код модуля A:
- импортирует подмодуль модуля B (`<pkg>.B._app`, `<pkg>.B.x`) — нужно `from <pkg>.B import …`;
- импортирует из B имя, которого нет в `B.__all__` (или имя с `_`);
- образует цикл зависимостей между модулями.
Направление разрешённых связей задаёт `.importlinter` (module-deps). Файл защищён.
"""

from __future__ import annotations

import ast
import configparser
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
MODULE_DEPTH = 2  # <pkg>.<модуль>: всё глубже — внутренности модуля


def root_package() -> Path | None:
    packages = [p for p in SRC.iterdir() if (p / "__init__.py").exists()] if SRC.exists() else []
    return packages[0] if len(packages) == 1 else None


def public_names(module_dir: Path) -> set[str]:
    tree = ast.parse((module_dir / "__init__.py").read_text())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return {
                e.value
                for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
    return set()


def imports(path: Path, pkg: str) -> list[tuple[str, list[str], int]]:
    """(абсолютный модуль, импортируемые имена, строка) для импортов внутри пакета."""
    rel = path.relative_to(SRC).with_suffix("").parts
    base = list(rel[:-1])
    found: list[tuple[str, list[str], int]] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found += [(a.name, [], node.lineno) for a in node.names if a.name.startswith(pkg + ".")]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = base[: len(base) - node.level + 1]
                mod = ".".join([*anchor, node.module] if node.module else anchor)
            else:
                mod = node.module or ""
            if mod == pkg or mod.startswith(pkg + "."):
                found.append((mod, [a.name for a in node.names], node.lineno))
    return found


def declared_modules(pkg: str) -> dict[str, set[str]]:
    """Модули из .importlinter: {контракт.ключ: {модуль}} для containers и layers."""
    path = ROOT / ".importlinter"
    if not path.exists():
        return {}
    config = configparser.ConfigParser()
    config.read(path)
    result: dict[str, set[str]] = {}
    for section in config.sections():
        for key in ("containers", "layers"):
            raw = config.get(section, key, fallback="")
            names = {
                line.strip().split(".")[1]
                for line in raw.splitlines()
                if line.strip().startswith(pkg + ".") and line.strip().count(".") == 1
            }
            if names:
                result[f"{section.split(':')[-1]}.{key}"] = names
    return result


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if state.get(nxt) == 1:
                return [*stack[stack.index(nxt) :], nxt]
            if nxt not in state and (cycle := visit(nxt)):
                return cycle
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(graph):
        if node not in state and (cycle := visit(node)):
            return cycle
    return None


def main() -> int:
    package = root_package()
    if package is None:
        print("boundaries: пропуск (нет единственного пакета в src/)")
        return 0
    pkg = package.name
    modules = {p.name: p for p in package.iterdir() if (p / "__init__.py").exists()}
    publics = {name: public_names(path) for name, path in modules.items()}
    graph: dict[str, set[str]] = {m: set() for m in modules}
    errors: list[str] = []
    for owner, path in modules.items():
        for file in sorted(path.rglob("*.py")):
            where = file.relative_to(ROOT).as_posix()
            for mod, names, line in imports(file, pkg):
                parts = mod.split(".")
                if len(parts) < MODULE_DEPTH or parts[1] not in modules or parts[1] == owner:
                    continue
                target = parts[1]
                graph[owner].add(target)
                if len(parts) > MODULE_DEPTH:
                    errors.append(
                        f"{where}:{line}: импорт внутренностей модуля `{target}` ({mod}) — "
                        f"используйте публичный API: from {pkg}.{target} import …"
                    )
                hidden = [n for n in names if n.startswith("_") or n not in publics[target]]
                if len(parts) == MODULE_DEPTH and hidden:
                    errors.append(
                        f"{where}:{line}: {hidden} не входят в публичный API `{target}` "
                        f"(__all__ = {sorted(publics[target])})"
                    )
    business = {m for m, path in modules.items() if (path / "_domain.py").exists()}
    for contract, names in declared_modules(pkg).items():
        # containers (слои внутри модуля) — только бизнес-модули с _domain; прочее — все модули
        expected = business if contract.endswith(".containers") else set(modules)
        missing = sorted(expected - names)
        ghost = sorted(names - set(modules))
        if missing:
            errors.append(
                f".importlinter [{contract}]: модули {missing} не внесены — их правила "
                "не проверяются (добавить по ADR, решение человека)"
            )
        if ghost:
            errors.append(
                f".importlinter [{contract}]: модулей {ghost} нет в коде — убрать из правил"
            )
    if cycle := find_cycle(graph):
        errors.append("цикл зависимостей между модулями: " + " → ".join(cycle))
    if errors:
        print("Нарушены границы модулей:\n" + "\n".join(f"  {e}" for e in errors))
        return 1
    links = sum(len(v) for v in graph.values())
    print(f"boundaries: ok ({len(modules)} модулей, {links} связей)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
