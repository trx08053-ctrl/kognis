#!/usr/bin/env python3
"""commit-msg hook: Conventional Commits (https://www.conventionalcommits.org)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\([\w./-]+\))?!?: \S.{0,99}$"
)
PASSTHROUGH = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")


def main() -> int:
    subject = Path(sys.argv[1]).read_text().splitlines()[0].strip() if len(sys.argv) > 1 else ""
    if subject.startswith(PASSTHROUGH) or PATTERN.match(subject):
        return 0
    print(
        f"Сообщение коммита не по Conventional Commits: {subject!r}\n"
        "Формат: <type>(<scope>)?: <описание>, type ∈ feat|fix|docs|style|refactor|perf|"
        "test|build|ci|chore|revert; описание — до 100 символов (подробности — в теле коммита). "
        "Пример: feat(api): add order export [demo-1xd]"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
