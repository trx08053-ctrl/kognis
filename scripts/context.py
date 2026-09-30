#!/usr/bin/env python3
"""Компактный контекст одного модуля для агента — без вызова модели.

    context.py <модуль> [--full] [--budget СИМВОЛОВ]

По умолчанию выдача ограничена бюджетом (≈ 2 тыс. токенов): длинные списки и карточка сокращаются,
и это всегда сказано явно («показаны 10 из 38 — …»); --full — всё.

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
DEFAULT_BUDGET = 6000
LIST_LIMIT = 10


def shown(items: list[str], full: bool, what: str, name: str) -> list[str]:
    if full or len(items) <= LIST_LIMIT:
        return items
    rest = f"- … показаны {LIST_LIMIT} из {len(items)} {what}: `just context {name} --full`"
    return [*items[:LIST_LIMIT], rest]


def main() -> int:
    args = sys.argv[1:]
    full = "--full" in args
    budget = int(args[args.index("--budget") + 1]) if "--budget" in args else DEFAULT_BUDGET
    name = next((a for a in args if not a.startswith("--") and not a.isdigit()), "")
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
    card_text = card.read_text().strip() if card.exists() else "**нет карточки** — just module-card"
    out.append(card_text)
    out += ["", "## Из кода", "Публичный API:"]
    api = [f"- `{n}` — `{where}`" for n, where in comp.public]
    out += shown(api, full, "публичных имён", name) or ["- —"]
    out.append(f"Использует модули: {', '.join(sorted(comp.deps)) or '—'}")
    out.append(f"Используется модулями: {', '.join(used_by) or '—'}")
    out.append("Тесты:")
    out += shown([f"- `{t}`" for t in sorted(comp.tests)], full, "тестов", name) or ["- **нет**"]
    out.append("ADR: " + (", ".join(adrs) or "—"))
    out += [
        "",
        "## Как проверять",
        f"- во время работы: `just test-module {name}`",
        "- перед «готово»: `just verify`; закрытие — `just task-done <id>` (сам прогоняет verify)",
        "- изменения за пределами модуля: сверить с TASK — `just scope <id>`",
    ]
    text = "\n".join(out)
    if not full and len(text) > budget:  # сокращаем карточку, а не факты из кода
        cut = max(len(card_text) - (len(text) - budget), 600)
        short = card_text[:cut].rsplit("\n", 1)[0]
        note = (f"\n\n… карточка сокращена до бюджета ({budget} символов): полностью — "
                f"`{gen_map.rel(card)}` или `just context {name} --full`")  # fmt: skip
        text = text.replace(card_text, short + note, 1)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
