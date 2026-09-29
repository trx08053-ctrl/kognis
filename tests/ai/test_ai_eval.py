"""Оценка качества разбора (kognis-3fl): `scripts/ai_eval.py` так, как его запускает человек."""

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import pytest

from kognis.analysis import Analysis, AnalysisOutcome, AnalysisResult, Pattern
from kognis.safety import HelpBlock, help_block

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ai_eval.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ai_eval", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ai_eval"] = module
    spec.loader.exec_module(module)
    return module


def run_cli(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    results = tmp_path / "results.jsonl"
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--results", str(results), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    return done, results


def last_line(results: Path) -> dict[str, Any]:
    line: dict[str, Any] = json.loads(results.read_text(encoding="utf-8").splitlines()[-1])
    return line


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return load_script()


@pytest.mark.acceptance("kognis-3fl", "AC1")
def test_fake_run_passes_every_case_and_writes_report(tmp_path: Path) -> None:
    done, results = run_cli(tmp_path, "--provider", "fake", "--direction", "all")
    assert done.returncode == 0, done.stdout + done.stderr
    cases = sorted(p.stem for p in (ROOT / "evals" / "ai" / "cases").glob("*.json"))
    assert len(cases) >= 10
    assert all(name in done.stdout for name in cases)
    assert "FAIL" not in done.stdout
    line = last_line(results)
    assert line["model"] == "fake"
    assert line["share"] == 1.0
    assert line["cases"] == len(cases) * 5
    assert line["date"]


@pytest.mark.acceptance("kognis-3fl", "AC1")
@pytest.mark.parametrize(
    ("defect", "failed"),
    [
        ("invalid-json", "json_schema"),
        ("invented-quote", "grounding"),
        ("invented-id", "grounding"),
        ("diagnosis", "no_diagnosis"),
        ("medication", "no_diagnosis"),
        ("english", "russian"),
    ],
)
def test_broken_answer_fails_the_matching_check(tmp_path: Path, defect: str, failed: str) -> None:
    done, results = run_cli(tmp_path, "--case", "anxiety-work", "--fake-defect", defect)
    assert done.returncode == 1
    line = last_line(results)
    names = [str(item) for item in line["failed"]]
    assert any(item.endswith(":" + failed) for item in names), names
    assert "FAIL" in done.stdout


@pytest.mark.acceptance("kognis-3fl", "AC1")
def test_missing_questions_and_slow_answer_are_caught(script: ModuleType) -> None:
    case = next(c for c in script.load_cases() if c.id == "little-data")
    result = AnalysisResult.model_validate(
        {"summary": "Кратко.", "patterns": [], "questions": ["Утверждение без вопроса"]}
    )
    assert script.check_questions(result).ok is False
    seen = script.Observed(None, [], 100.0, {})
    names = {c.name: c.ok for c in script.evaluate(case, seen, 60.0)}
    assert names["latency"] is False
    assert names["json_schema"] is False


def outcome(
    status: Literal["done", "crisis"], result: AnalysisResult | None, help_block_: HelpBlock | None
) -> AnalysisOutcome:
    day = date(2026, 9, 1)
    analysis = Analysis(1, 1, None, "cbt", day, day, status, result, ())
    return AnalysisOutcome(analysis, help_block_)


@pytest.mark.acceptance("kognis-3fl", "AC2")
def test_crisis_cases_pass_through_the_service(tmp_path: Path) -> None:
    done, results = run_cli(tmp_path, "--case", "crisis", "--case", "crisis-reflection")
    assert done.returncode == 0, done.stdout
    assert "FAIL" not in done.stdout
    assert last_line(results)["cases"] == 2


@pytest.mark.acceptance("kognis-3fl", "AC2")
def test_crisis_check_tells_support_from_patterns(script: ModuleType) -> None:
    pattern = Pattern(title="Т", description="О", entry_ids=[1], quotes=[])
    with_patterns = AnalysisResult(summary="С", patterns=[pattern], questions=[])
    good = outcome("crisis", None, help_block())
    assert script.check_crisis(good, 0).ok
    assert not script.check_crisis(outcome("done", with_patterns, None), 1).ok
    assert not script.check_crisis(outcome("crisis", with_patterns, help_block()), 0).ok
    assert not script.check_crisis(outcome("crisis", None, None), 0).ok
    assert not script.check_crisis(outcome("crisis", None, HelpBlock("Вы не одни", ())), 0).ok
    assert not script.check_crisis(good, 1).ok


def test_bad_arguments_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOGNIS_AI_BASE_URL", raising=False)
    done, results = run_cli(tmp_path, "--provider", "env")
    assert done.returncode == 2
    assert "KOGNIS_AI_BASE_URL" in done.stderr
    assert not results.exists()
    assert run_cli(tmp_path, "--direction", "nope")[0].returncode == 2
    assert run_cli(tmp_path, "--case", "nope")[0].returncode == 2
