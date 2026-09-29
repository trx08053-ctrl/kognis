"""Структура слоя web: kognis-pj6 AC1 — файлы короткие, роутер каждой области в своём файле."""

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "src" / "kognis" / "web"
MAX_LINES = 400


@pytest.mark.source
@pytest.mark.acceptance("kognis-pj6", "AC1")
def test_no_web_file_is_too_long() -> None:
    long = {
        p.name: n for p in WEB.glob("*.py") if (n := len(p.read_text().splitlines())) > MAX_LINES
    }
    assert long == {}


@pytest.mark.source
@pytest.mark.acceptance("kognis-pj6", "AC1")
def test_each_router_lives_in_its_own_file() -> None:
    routers = {
        p.name: re.findall(r"^def (\w+_router)\(", p.read_text(), re.M) for p in WEB.glob("*.py")
    }
    found = {name: rs for name, rs in routers.items() if rs}
    assert all(len(rs) == 1 for rs in found.values()), found
    assert len(found) == 8, found
    assert "_app.py" not in found  # _app.py только собирает приложение
