"""Структура фронтенда: kognis-dwx — страница в файле, типы API только из схемы бэкенда."""

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
MAX_LINES = 500
PAGES = ["Auth", "Home", "DayReview", "Analysis", "Quests", "Profile"]


@pytest.mark.source
@pytest.mark.acceptance("kognis-dwx", "AC1")
def test_no_frontend_file_is_too_long() -> None:
    long = {
        str(p.relative_to(SRC)): n
        for p in SRC.rglob("*.ts*")
        if (n := len(p.read_text().splitlines())) > MAX_LINES
    }
    assert long == {}


@pytest.mark.source
@pytest.mark.acceptance("kognis-dwx", "AC1")
def test_each_page_lives_in_pages_and_shared_parts_in_components() -> None:
    for page in PAGES:
        assert (SRC / "pages" / f"{page}Page.tsx").is_file(), page
    assert list((SRC / "components").glob("*.tsx")), "нет общих компонентов"


@pytest.mark.source
@pytest.mark.acceptance("kognis-dwx", "AC1")
def test_app_only_holds_routes_and_shell() -> None:
    components = re.findall(
        r"^(?:export )?function ([A-Z]\w*)", (SRC / "App.tsx").read_text(), re.M
    )
    assert components == ["App"]


@pytest.mark.source
@pytest.mark.acceptance("kognis-dwx", "AC2")
def test_api_types_come_from_generated_schema() -> None:
    api = (SRC / "api.ts").read_text()
    assert 'from "./api.gen"' in api
    assert re.findall(r"^\s*(?:export )?interface \w+", api, re.M) == []
    assert re.findall(r"^export type (\w+) = \{", api, re.M) == []  # ручной объект вместо схемы


@pytest.mark.source
@pytest.mark.acceptance("kognis-dwx", "AC2")
def test_every_schema_used_in_api_exists_in_generated_types() -> None:
    api = (SRC / "api.ts").read_text()
    generated = (SRC / "api.gen.ts").read_text()
    used = set(re.findall(r'Schemas\["(\w+)"\]', api))
    defined = set(re.findall(r"^    (\w+): \{$", generated, re.M))
    assert used, "api.ts не использует схемы"
    assert used <= defined, used - defined
