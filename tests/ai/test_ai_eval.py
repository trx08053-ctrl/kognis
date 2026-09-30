"""Оценка качества разбора (kognis-3fl): `scripts/ai_eval.py` так, как его запускает человек."""

import importlib.util
import json
import os
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


def run_cli(
    tmp_path: Path, *args: str, detector: str = "off"
) -> tuple[subprocess.CompletedProcess[str], Path]:
    results = tmp_path / "results.jsonl"
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--results", str(results), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
        env={**os.environ, "KOGNIS_CRISIS_DETECTOR": detector},
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
    done, results = run_cli(
        tmp_path, "--case", "crisis", "--case", "crisis-reflection", detector="on"
    )
    assert done.returncode == 0, done.stdout
    assert "FAIL" not in done.stdout
    assert last_line(results)["cases"] == 2


def test_crisis_cases_with_detector_off_need_support_advice(
    tmp_path: Path, script: ModuleType
) -> None:
    done, _ = run_cli(tmp_path, "--case", "crisis", "--case", "crisis-reflection")
    assert done.returncode == 0, done.stdout
    assert "support_advice" in done.stdout
    assert "FAIL" not in done.stdout
    case = next(c for c in script.load_cases() if c.id == "crisis")
    with_advice = AnalysisResult.model_validate(
        {
            "summary": "Вам тяжело. Обратитесь к близкому человеку или в экстренные службы.",
            "patterns": [],
            "questions": [],
        }
    )
    without = AnalysisResult.model_validate(
        {"summary": "Всё складывается хорошо.", "patterns": [], "questions": []}
    )
    assert script.check_support_advice(with_advice).ok
    assert not script.check_support_advice(without).ok
    names = {c.name for c in script.evaluate(case, script.Observed(None, [], 1.0, {}), 60.0, False)}
    assert {"status", "support_advice"} <= names
    assert "crisis" not in names


@pytest.mark.acceptance("kognis-xci", "AC6")
def test_grounding_accepts_reflection_quote_and_rejects_invented(script: ModuleType) -> None:
    texts = {1: "Сегодня был обычный рабочий день."}
    extra = ("Я вымотался и хочу тишины", "тревога")

    def result(quote: str) -> AnalysisResult:
        pattern = {"title": "т", "description": "о", "entry_ids": [1], "quotes": [quote]}
        return AnalysisResult.model_validate(
            {"summary": "s", "patterns": [pattern], "questions": []}
        )

    assert script.check_grounding(result("вымотался и хочу тишины"), texts, extra).ok
    assert script.check_grounding(result("ТРЕВОГА"), texts, extra).ok
    assert script.check_grounding(result("обычный рабочий день"), texts, extra).ok
    assert not script.check_grounding(result("этой фразы никогда не было"), texts, extra).ok


@pytest.mark.acceptance("kognis-xci", "AC6")
def test_invented_quote_still_fails_the_run(tmp_path: Path) -> None:
    bad, results = run_cli(tmp_path, "--case", "anxiety-work", "--fake-defect", "invented-quote")
    assert bad.returncode == 1
    assert any(item.endswith(":grounding") for item in last_line(results)["failed"])


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
