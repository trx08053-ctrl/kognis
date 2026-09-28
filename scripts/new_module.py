#!/usr/bin/env python3
"""Новый бизнес-модуль корневого пакета или карточка для существующего.

    new_module.py <name> [--card-only]

Создаёт src/<pkg>/<name>/ (__init__.py — публичный API, _domain.py, _app.py, _infra.py)
и docs/modules/<name>.md. Напоминает про .importlinter и ARCHITECTURE.md (границы — ADR).
Файл защищён.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--card-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name):
        sys.exit("имя компонента: snake_case, латиница")
    packages = [p for p in (ROOT / "src").iterdir() if (p / "__init__.py").exists()]
    if len(packages) != 1:
        sys.exit("ожидался один пакет в src/")
    pkg = packages[0]
    comp = pkg / args.name
    if not args.card_only and not comp.exists() and not comp.with_suffix(".py").exists():
        comp.mkdir()
        (comp / "__init__.py").write_text(
            f'"""Модуль {args.name}: TODO ответственность (одно предложение)."""\n\n'
            "__all__: list[str] = []\n"
        )
        (comp / "_domain.py").write_text('"""Бизнес-правила: без ввода-вывода."""\n')
        (comp / "_app.py").write_text(
            '"""Сценарии модуля; публичное — реэкспорт в __init__.py."""\n'
        )
        # все три слоя: import-linter требует каждый слой в каждом контейнере
        (comp / "_infra.py").write_text('"""Хранение и внешние системы (адаптеры)."""\n')
        print(f"создано: {comp.relative_to(ROOT)}/ (__init__.py, _domain.py, _app.py, _infra.py)")
    card = ROOT / "docs" / "modules" / f"{args.name}.md"
    if card.exists():
        print(f"карточка уже есть: {card.relative_to(ROOT)}")
    else:
        card.parent.mkdir(parents=True, exist_ok=True)
        template = (ROOT / "docs" / "templates" / "MODULE_CARD.md").read_text()
        text = template.replace("<name>", args.name).replace("<pkg>", pkg.name)
        text = text.replace(
            "| … | `<name>` | … | только `<name>` (иначе — исключение через ADR) |",
            f"| … | `{args.name}` | … | только `{args.name}` |",
        )
        card.write_text(text)
        print(f"создано: {card.relative_to(ROOT)}")
    print(
        "Дальше: 1) добавить модуль в .importlinter (containers и module-deps) — защищённый файл, "
        "решение человека + ADR; 2) строка в docs/ARCHITECTURE.md; 3) just map; 4) tests/<модуль>/."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
