#!/usr/bin/env python3
"""Размер файлов исходного кода: не больше LIMIT строк. Файл защищён.

Большой файл — признак смешанных ответственностей (все роутеры или все страницы в одном месте):
его трудно читать агенту и человеку, правки конфликтуют. Тесты и сгенерированное не проверяются.
Разделяй по областям: роутер на область, страница на файл, общие компоненты отдельно.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 500
SOURCES = [("src", {".py"}), ("frontend/src", {".ts", ".tsx"})]
GENERATED = ("auto-generated", "автоматически сгенерирован", "не редактировать вручную")


def is_generated(text: str) -> bool:
    head = "\n".join(text.splitlines()[:5]).lower()
    return any(mark in head for mark in GENERATED)


def main() -> int:
    too_big: list[str] = []
    for folder, suffixes in SOURCES:
        base = ROOT / folder
        paths = sorted(base.rglob("*")) if base.is_dir() else []
        for path in paths:
            if path.suffix not in suffixes or ".test." in path.name or "__pycache__" in path.parts:
                continue
            text = path.read_text()
            lines = text.count("\n") + 1
            if lines > LIMIT and not is_generated(text):
                too_big.append(f"{path.relative_to(ROOT)}: {lines} строк")
    if too_big:
        print(f"Файлы длиннее {LIMIT} строк — разделите по областям ответственности:")
        print("\n".join(f"  - {item}" for item in too_big))
        return 1
    print(f"size: ok (≤ {LIMIT} строк)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
