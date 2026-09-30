#!/usr/bin/env python3
"""Найти модуль по формулировке задачи — без вызова модели. Файл защищён.

    locate.py "после переноса сделки пропадает история"  [--top 4]

Сопоставляет слова задачи (с грубым усечением окончаний) с источниками и объясняет выбор модуля:
карточки (термины и синонимы весят больше всего, затем назначение, сценарии, точки входа), публичные
имена, маршруты API (модуль — по имени роутера или его импортам), страницы фронтенда (через вызовы
/api/…), тесты и заголовки прошлых задач с их областью влияния. Дальше — `just context <модуль>`.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_map

ROOT = gen_map.ROOT
WORD = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9]+")
STOP = frozenset(
    [
        "и",
        "в",
        "во",
        "на",
        "с",
        "со",
        "после",
        "при",
        "для",
        "по",
        "из",
        "от",
        "до",
        "не",
        "ни",
        "что",
        "как",
        "это",
        "или",
        "а",
        "но",
        "же",
        "ли",
        "бы",
        "то",
        "его",
        "её",
        "их",
        "мы",
        "вы",
        "они",
        "он",
        "она",
        "оно",
        "я",
        "ты",
        "у",
        "к",
        "о",
        "об",
        "над",
        "под",
        "за",
        "про",
        "без",
        "между",
        "нет",
        "да",
        "все",
        "всё",
        "уже",
        "ещё",
        "когда",
        "где",
        "там",
        "тут",
        "может",
        "могут",
        "можно",
        "нужно",
        "надо",
        "есть",
        "быть",
        "был",
        "была",
        "были",
        "стал",
        "стала",
        "делать",
        "сделать",
        "работает",
        "показывает",
        "происходит",
        "появляется",
        "пропадает",
        "теперь",
        "снова",
        "сразу",
        "очень",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "for",
        "and",
        "or",
        "is",
        "are",
        "be",
        "with",
        "by",
        "from",
        "at",
        "as",
        "it",
        "this",
        "that",
        "not",
        "no",
    ]
)
ROUTE = re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*[\"']([^\"']*)[\"']")
PREFIX = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']")
API_CALL = re.compile(r"[\"'`](/api/[A-Za-z0-9_/-]*)")
TS_EXPORT = re.compile(r"(?:const|function|let)\s+(\w+)")
TS_IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from\s*[\"'][./]*[\w/]*api[\"']")
MIN_WORD = 3  # короче — шум
SHOW_ENTRIES, SHOW_TESTS, SHOW_WHY = 4, 3, 5
STEM_FROM = 5  # длиннее — отрезаем окончание (грубая основа слова для русского)
CARD_WEIGHTS = {"Термины": 4, "Назначение": 2, "Сценарии": 2, "Точки входа": 2}


def stems(text: str) -> set[str]:
    words: set[str] = set()
    for raw in WORD.findall(re.sub(r"([a-z])([A-Z])", r"\1 \2", text).replace("_", " ")):
        w = raw.lower().replace("ё", "е")
        if len(w) >= MIN_WORD and w not in STOP:
            words.add(w[: max(4, len(w) - 2)] if len(w) > STEM_FROM else w)
    return words


class Index:
    def __init__(self) -> None:
        pkg, comps = gen_map.collect()
        self.pkg = pkg
        self.modules = {c.name: c for c in comps}
        # платформенные модули (web, db — без _domain.py) касаются всего и только шумят в выдаче
        self.business = {c.name for c in comps if (c.path / "_domain.py").exists()}
        self.hits: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self.weight: dict[tuple[str, str], int] = {}
        self.entries: dict[str, set[str]] = defaultdict(set)
        self.tests: dict[str, set[str]] = defaultdict(set)
        self.route_owner: dict[str, set[str]] = {}

    def add(self, module: str, source: str, text: str, weight: int) -> None:
        for s in stems(text):
            self.hits[module][s].add(source)
            self.weight[(source, s)] = max(self.weight.get((source, s), 0), weight)

    def build(self) -> Index:
        for name, comp in self.modules.items():
            self.cards(name)
            self.add(name, f"модуль {name}", name + " " + " ".join(n for n, _ in comp.public), 2)
            for test in sorted(comp.tests):
                self.tests[name].add(test)
                self.add(name, f"тест {test}", Path(test).stem, 1)
        self.routes()
        self.frontend()
        self.tasks()
        return self

    def cards(self, name: str) -> None:
        card = gen_map.CARDS / f"{name}.md"
        for line in card.read_text().splitlines() if card.exists() else []:
            label = next((k for k in CARD_WEIGHTS if f"**{k}" in line), "")
            self.add(name, f"карточка: {label or 'текст'}", line, CARD_WEIGHTS.get(label, 1))

    def routes(self) -> None:
        for path in sorted((ROOT / "src").rglob("*.py")):
            text = path.read_text()
            found = ROUTE.findall(text)
            if not found:
                continue
            prefix = next(iter(PREFIX.findall(text)), "")
            imported = set(re.findall(rf"from {self.pkg}\.(\w+) import", text)) & self.business
            for method, sub in found:
                route = f"{method.upper()} {prefix}{sub}"
                # владелец — модуль из имени файла-роутера или пути (`_analysis.py`, /api/analyses),
                # иначе все бизнес-модули, которые файл импортирует
                named = {m for m in self.business if m[:5] in (path.stem + prefix + sub).lower()}
                owners = named or imported
                self.route_owner[prefix + sub] = owners
                for m in owners:
                    self.entries[m].add(f"{route} ({gen_map.rel(path)})")
                    self.add(m, f"маршрут {route}", prefix + sub, 2)

    def owners_of(self, calls: list[str]) -> set[str]:
        owners: set[str] = set()
        for call in calls:
            for route, mods in self.route_owner.items():
                if call.rstrip("/") and route.startswith(call.rstrip("/").split("{")[0]):
                    owners |= mods
        return owners

    def frontend(self) -> None:
        src = ROOT / "frontend" / "src"
        files = (
            [p for p in sorted(src.rglob("*.ts*")) if ".test." not in p.name]
            if src.is_dir()
            else []
        )
        # функции клиента API (api.ts): имя → маршруты, чтобы связать страницы с модулями
        api_funcs: dict[str, list[str]] = {}
        for p in (p for p in files if p.suffix == ".ts"):
            for part in p.read_text().split("\nexport ")[
                1:
            ]:  # `export const f = …` и `export function f`
                name = TS_EXPORT.match(part.removeprefix("async "))
                if name:
                    api_funcs[name.group(1)] = API_CALL.findall(part)
        for path in files:
            if path.suffix != ".tsx":
                continue
            text = path.read_text()
            used = [
                n.strip().split(" as ")[0]
                for grp in TS_IMPORT.findall(text)
                for n in grp.split(",")
            ]
            calls = API_CALL.findall(text) + [c for n in used for c in api_funcs.get(n, [])]
            owners = self.owners_of(calls)
            visible = " ".join(re.findall(r"[А-Яа-яЁё][А-Яа-яЁё ,.-]{2,80}", text))
            for m in owners:
                self.entries[m].add(f"страница {gen_map.rel(path)}")
                self.add(m, f"страница {path.name}", path.stem + " " + visible, 1)

    def tasks(self) -> None:
        for task in sorted((ROOT / "tasks").glob("*/TASK.md")):
            text = task.read_text()
            title = text.splitlines()[0] if text else ""
            scope = next((ln for ln in text.splitlines() if "**Модули:**" in ln), "")
            mods = [m for m in self.modules if re.search(rf"\b{m}\b", scope)]
            for m in mods:
                self.add(m, f"задача {task.parent.name}: {title[7:70]}", title, 2)

    def rank(self, query: str, top: int) -> list[tuple[str, int, list[str]]]:
        wanted = stems(query)
        ranked: list[tuple[str, int, list[str]]] = []
        for module, by_stem in self.hits.items():
            if module not in self.business:
                continue
            score, why = 0, list[str]()
            for s in wanted & set(by_stem):
                best = max(by_stem[s], key=lambda src: self.weight[(src, s)])
                score += self.weight[(best, s)]
                why.append(f"«{s}…» — {best}")
            if score:
                ranked.append((module, score, why))
        return sorted(ranked, key=lambda r: -r[1])[:top]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 4
    if not args:
        print(__doc__)
        return 2
    query = " ".join(a for a in args if not a.isdigit())
    index = Index().build()
    ranked = index.rank(query, top)
    if not ranked:
        print("совпадений нет — уточните формулировку или смотрите docs/MAP.md; "
              "добавьте термины в карточки модулей (поле «Термины и синонимы»)")  # fmt: skip
        return 1
    for module, score, why in ranked:
        print(f"## {module}  (совпадение {score})")
        print("  почему: " + "; ".join(why[:SHOW_WHY]))
        entries = sorted(index.entries[module])
        if entries:
            more = " …" if len(entries) > SHOW_ENTRIES else ""
            print("  точки входа: " + "; ".join(entries[:SHOW_ENTRIES]) + more)
        tests = sorted(index.tests[module])
        if tests:
            print(
                "  тесты: "
                + ", ".join(tests[:SHOW_TESTS])
                + (" …" if len(tests) > SHOW_TESTS else "")
            )
        print(f"  дальше: just context {module}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
