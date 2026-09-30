#!/usr/bin/env python3
"""Текст для человека — только в словарях (docs/I18N.md). Файл защищён.

    check_i18n.py            проверка: нет нового текста прямо в коде
    check_i18n.py --adopt    однократно для существующего проекта: записать текущие находки в планку
                             (решение человека: hook спрашивает подтверждение)

Находка — строка, которую увидит пользователь, вне словарей:
- фронтенд (`frontend/src`, кроме тестов, `i18n/`, `api.gen.ts`): строка с буквами не-латиницы,
  текст между JSX-тегами и атрибуты placeholder/title/alt/aria-label/label с английскими словами;
- HTML-шаблоны сервера (`src/**/templates`): текст между тегами вне `{{ … }}`/`{% … %}`;
- Python (`src/`, кроме `i18n/`, `locales/`, `*i18n.py`): строковые литералы с буквами не-латиницы,
  кроме docstring и вызовов логирования. Английский текст в Python не распознаётся — поэтому код
  разработчика пишется по-английски, а наружу уходят коды ошибок.

Существующий проект: `--adopt` фиксирует найденное в `.quality-baseline.json` (`i18n_hardcoded`) —
это долг перевода. Новые находки запрещены, исправленные уходят из планки при `just ratchet-up`.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".quality-baseline.json"
KEY = "i18n_hardcoded"
CATALOG_DIRS = {"i18n", "locales"}
LOG_NAMES = {"log", "logger", "logging", "_log", "LOG", "LOGGER"}
SHOW = 30
NON_LATIN = re.compile(r"[^\W\d_A-Za-z]")  # буква, но не ASCII-латиница
JSX_TEXT = re.compile(r"(?<![=-])>\s*([A-Za-z][A-Za-z0-9 ,.!?'’:;-]*?)\s*<")
JSX_ATTR = re.compile(
    r"\b(?:placeholder|title|alt|aria-label|label)=\"([^\"]*[A-Za-z]{2,}[^\"]*)\""
)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(^|\s)//.*$", re.M)
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)
HTML_TEXT = re.compile(r">([^<>]*[^\W\d_][^<>]*)<")
SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)

Finding = tuple[str, int, str]  # путь, строка, текст


def is_catalog(path: Path) -> bool:
    return bool(CATALOG_DIRS & set(path.parts)) or path.stem.endswith("i18n")


def keep_lines(text: str, pattern: re.Pattern[str]) -> str:
    """Убрать совпадения, сохранив переводы строк (номера строк не сдвигаются)."""
    return pattern.sub(lambda m: "\n" * m.group(0).count("\n") + " ", text)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan_frontend(path: Path, rel: str) -> list[Finding]:
    text = keep_lines(keep_lines(path.read_text(), BLOCK_COMMENT), LINE_COMMENT)
    found: list[Finding] = [
        (rel, n, line.strip())
        for n, line in enumerate(text.splitlines(), 1)
        if NON_LATIN.search(line)
    ]
    if path.suffix == ".tsx":
        for pattern in (JSX_TEXT, JSX_ATTR):
            for m in pattern.finditer(text):
                n = line_of(text, m.start(1))
                if not any(f[1] == n for f in found):
                    found.append((rel, n, m.group(1).strip()))
    return found


def scan_template(path: Path, rel: str) -> list[Finding]:
    text = keep_lines(keep_lines(path.read_text(), SCRIPT_STYLE), JINJA)
    return [
        (rel, line_of(text, m.start(1)), m.group(1).strip())
        for m in HTML_TEXT.finditer(text)
        if m.group(1).strip()
    ]


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _log_args(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id in LOG_NAMES:
            ids |= {id(sub) for arg in node.args for sub in ast.walk(arg)}
    return ids


def scan_python(path: Path, rel: str) -> list[Finding]:
    tree = ast.parse(path.read_text())
    skip = _docstrings(tree) | _log_args(tree)
    return [
        (rel, node.lineno, node.value.strip()[:80])
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in skip
        and NON_LATIN.search(node.value)
    ]


def scan() -> list[Finding]:
    found: list[Finding] = []
    front = ROOT / "frontend" / "src"
    for path in sorted(front.rglob("*.ts*")) if front.is_dir() else []:
        rel = path.relative_to(ROOT).as_posix()
        if (
            ".test." in path.name
            or path.name == "api.gen.ts"
            or is_catalog(path.relative_to(front))
        ):
            continue
        found += scan_frontend(path, rel)
    src = ROOT / "src"
    for path in sorted(src.rglob("*")) if src.is_dir() else []:
        rel = path.relative_to(ROOT).as_posix()
        if "__pycache__" in path.parts or is_catalog(path.relative_to(src)):
            continue
        if path.suffix == ".py":
            found += scan_python(path, rel)
        elif path.suffix in {".html", ".jinja", ".j2"} and "templates" in path.parts:
            found += scan_template(path, rel)
    return sorted(found)


def entry(finding: Finding) -> str:
    """Запись планки без номера строки: сдвиг кода не считается изменением."""
    return f"{finding[0]}: {finding[2]}"


def load_baseline() -> tuple[dict[str, object], list[str] | None]:
    try:
        data = cast("dict[str, object]", json.loads(BASELINE.read_text()))
    except (OSError, ValueError):
        return {}, None
    raw = data.get(KEY)
    return data, [str(x) for x in cast("list[object]", raw)] if isinstance(raw, list) else None


def shrink(allowed: list[str]) -> list[str]:
    """Планка после исправлений: разрешённые находки, которые ещё есть в коде (для ratchet-up)."""
    left = Counter(entry(f) for f in scan())
    kept: list[str] = []
    for item in allowed:
        if left[item] > 0:
            left[item] -= 1
            kept.append(item)
    return kept


def main() -> int:
    data, allowed = load_baseline()
    found = scan()
    if "--adopt" in sys.argv:
        if allowed:  # пустая планка (новый проект) — можно; непустую только уменьшают
            sys.exit(f"планка {KEY} уже есть — её можно только уменьшать (just ratchet-up)")
        data[KEY] = [entry(f) for f in found]
        BASELINE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"i18n: в планку записано {len(found)} мест с текстом в коде — долг перевода")
        return 0
    budget = Counter(allowed or [])
    new: list[Finding] = []
    for f in found:
        if budget[entry(f)] > 0:
            budget[entry(f)] -= 1
        else:
            new.append(f)
    if new:
        print(f"Текст для человека прямо в коде ({len(new)}) — вынесите в словари (docs/I18N.md):")
        print("\n".join(f"  {p}:{n}: {t[:100]}" for p, n, t in new[:SHOW]))
        if len(new) > SHOW:
            print(f"  … и ещё {len(new) - SHOW}")
        print(
            'Интерфейс: t("ключ") и ключ во всех frontend/src/i18n/<язык>.ts; сервер: код '
            "ошибки (`detail.code`), текст — в словаре интерфейса; служебное — по-английски."
        )
        return 1
    debt = len(allowed or [])
    fixed = debt - (len(found) - len(new))
    hint = f", исправлено {fixed} — just ratchet-up" if fixed > 0 else ""
    print(f"i18n: ok (долг перевода в планке: {debt}{hint})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
