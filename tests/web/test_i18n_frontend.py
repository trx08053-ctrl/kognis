"""Основа мультиязычности фронтенда: приёмочные тесты kognis-i7j (AC1–AC3; AC4 — e2e/test_ui.py)."""

import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
# область задачи: общие компоненты и служебные модули (страницы и api.ts — следующие задачи серии)
IN_SCOPE = [
    "frontend/src/App.tsx",
    "frontend/src/main.tsx",
    "frontend/src/Icons.tsx",
    "frontend/src/theme.ts",
    "frontend/src/pagination.ts",
    "frontend/src/dates.ts",
    "frontend/src/privateCrypto.ts",
]


def check_i18n() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_i18n", ROOT / "scripts" / "check_i18n.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.source
@pytest.mark.acceptance("kognis-i7j", "AC1")
def test_shared_components_have_no_text_in_code() -> None:
    found = {path for path, _line, _text in check_i18n().scan()}
    scope = set(IN_SCOPE) | {
        p.relative_to(ROOT).as_posix() for p in (SRC / "components").glob("*.tsx")
    }
    assert found & scope == set()


@pytest.mark.source
@pytest.mark.acceptance("kognis-i7j", "AC1")
def test_dictionary_and_provider_exist_with_base_language() -> None:
    index = (SRC / "i18n" / "index.tsx").read_text()
    assert 'LOCALES: readonly Locale[] = ["ru"]' in index
    assert (SRC / "i18n" / "ru.ts").is_file()
    assert "<I18nProvider>" in (SRC / "main.tsx").read_text()


def run_vitest(name: str) -> None:
    pnpm = shutil.which("pnpm")
    assert pnpm, "нет pnpm"
    result = subprocess.run(
        [pnpm, "--dir", "frontend", "exec", "vitest", "run", "--coverage.enabled=false", name],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.source
@pytest.mark.acceptance("kognis-i7j", "AC2")
def test_switching_language_updates_shell_texts_and_html_lang() -> None:
    run_vitest("src/i18n.test.tsx")


@pytest.mark.source
@pytest.mark.acceptance("kognis-i7j", "AC3")
def test_dates_and_numbers_follow_language() -> None:
    run_vitest("src/i18n.test.tsx")
