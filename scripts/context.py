#!/usr/bin/env python3
"""Компактный контекст одного модуля для агента — без вызова модели.

    context.py <модуль>

Карточка модуля + из кода: публичный API, от кого зависит, кто использует, тесты,
связанные ADR и команды проверки. Начинать изменение — отсюда, а не со всей документации.
Файл защищён.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_map

ROOT = gen_map.ROOT


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    pkg, comps = gen_map.collect()
    comp = next((c for c in comps if c.name == name), None)
    if comp is None:
        sys.exit(f"нет модуля {name!r}; есть: {[c.name for c in comps]}")
    used_by = sorted(c.name for c in comps if name in c.deps)
    word = re.compile(rf"\b{re.escape(name)}\b")
    adrs = [
        p.relative_to(ROOT).as_posix()
        for p in sorted((ROOT / "docs" / "adr").glob("*.md"))
        if word.search(p.read_text())
    ]
    card = gen_map.CARDS / f"{name}.md"
    out = [f"# Контекст модуля `{pkg}.{name}`", "", f"Код: `{gen_map.rel(comp.path)}/`", ""]
    out.append("## Карточка (ответственность, правила, данные)")
    out.append(card.read_text().strip() if card.exists() else "**нет карточки** — just module-card")
    out += ["", "## Из кода", "Публичный API:"]
    out += [f"- `{n}` — `{where}`" for n, where in comp.public] or ["- —"]
    out.append(f"Использует модули: {', '.join(sorted(comp.deps)) or '—'}")
    out.append(f"Используется модулями: {', '.join(used_by) or '—'}")
    out.append("Тесты: " + (", ".join(f"`{t}`" for t in sorted(comp.tests)) or "**нет**"))
    out.append("ADR: " + (", ".join(adrs) or "—"))
    out += [
        "",
        "## Как проверять",
        f"- во время работы: `just test-module {name}`",
        "- перед «готово»: `just verify`; закрытие — `just task-done <id>` (сам прогоняет verify)",
        "- изменения за пределами модуля: сверить с TASK — `just scope <id>`",
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
