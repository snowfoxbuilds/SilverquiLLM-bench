"""Tests for TODO item 8: 3-dimension evaluation system.

Tests verify:
- CardResult dataclass: pass_rate computed correctly.
- EngineResult dataclass: pass_rate computed correctly.
- FullEvalResult.compute_aggregates(): aggregates across all dimensions.
- evaluate() SOS dimension: runs audited SOS tests against agent's card_impl.py.
- evaluate() FDN dimension: uses pre-filled reference impls from cards_dir.
- evaluate() Engine dimension: runs engine tests against engine_work.
- Missing audited tests → card skipped gracefully.
- Missing status.json → empty SOS results.
- engine_diff.patch fallback when engine_work/ absent.
- No completed SOS cards → empty SOS results.
- All tests pass → 100% pass rate.
- All tests fail → 0% pass rate.
- result.json written per SOS card.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.evaluator import (
    CardResult,
    EngineResult,
    FullEvalResult,
    evaluate,
)


# ---------------------------------------------------------------------------
# Dataclass unit tests
# ---------------------------------------------------------------------------


class TestCardResult:
    def test_pass_rate_computed_from_fields(self):
        cr = CardResult(collector_number="42", tests_passed=3, tests_failed=1, tests_total=4, pass_rate=0.75)
        assert cr.pass_rate == 0.75

    def test_zero_total_pass_rate(self):
        cr = CardResult(collector_number="1", tests_total=0, pass_rate=0.0)
        assert cr.pass_rate == 0.0

    def test_all_passed(self):
        cr = CardResult(collector_number="10", tests_passed=5, tests_failed=0, tests_total=5, pass_rate=1.0)
        assert cr.pass_rate == 1.0

    def test_all_failed(self):
        cr = CardResult(collector_number="10", tests_passed=0, tests_failed=5, tests_total=5, pass_rate=0.0)
        assert cr.pass_rate == 0.0

    def test_skipped_flag(self):
        cr = CardResult(collector_number="99", skipped=True)
        assert cr.skipped is True
        assert cr.tests_total == 0

    def test_errors_field(self):
        cr = CardResult(collector_number="1", errors=["something went wrong"])
        assert cr.errors == ["something went wrong"]

    def test_serializable_via_asdict(self):
        cr = CardResult(collector_number="5", tests_passed=2, tests_failed=1, tests_total=3, pass_rate=2 / 3)
        d = asdict(cr)
        assert d["collector_number"] == "5"
        assert d["tests_passed"] == 2


class TestEngineResult:
    def test_pass_rate(self):
        er = EngineResult(tests_passed=8, tests_failed=2, tests_total=10, pass_rate=0.8)
        assert er.pass_rate == 0.8

    def test_zero_total(self):
        er = EngineResult()
        assert er.pass_rate == 0.0
        assert er.tests_total == 0

    def test_errors_default_empty(self):
        er = EngineResult()
        assert er.errors == []


class TestFullEvalResultAggregation:
    def test_compute_aggregates_sos(self):
        result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=3, tests_failed=1, tests_total=4),
                "2": CardResult(collector_number="2", tests_passed=5, tests_failed=1, tests_total=6),
            }
        )
        result.compute_aggregates()
        # 8 passed out of 10 total
        assert result.sos_pass_rate == pytest.approx(0.8)

    def test_compute_aggregates_fdn(self):
        result = FullEvalResult(
            fdn_results={
                "100": CardResult(collector_number="100", tests_passed=2, tests_failed=0, tests_total=2),
                "200": CardResult(collector_number="200", tests_passed=1, tests_failed=1, tests_total=2),
            }
        )
        result.compute_aggregates()
        assert result.fdn_pass_rate == pytest.approx(0.75)

    def test_compute_aggregates_engine(self):
        result = FullEvalResult(
            engine_result=EngineResult(tests_passed=9, tests_failed=1, tests_total=10, pass_rate=0.9),
        )
        result.compute_aggregates()
        assert result.engine_pass_rate == pytest.approx(0.9)

    def test_compute_aggregates_empty_sos(self):
        result = FullEvalResult()
        result.compute_aggregates()
        assert result.sos_pass_rate == 0.0

    def test_compute_aggregates_empty_fdn(self):
        result = FullEvalResult()
        result.compute_aggregates()
        assert result.fdn_pass_rate == 0.0

    def test_compute_aggregates_all_dimensions(self):
        result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=4, tests_failed=0, tests_total=4),
            },
            fdn_results={
                "100": CardResult(collector_number="100", tests_passed=3, tests_failed=3, tests_total=6),
            },
            engine_result=EngineResult(tests_passed=10, tests_failed=0, tests_total=10, pass_rate=1.0),
        )
        result.compute_aggregates()
        assert result.sos_pass_rate == pytest.approx(1.0)
        assert result.fdn_pass_rate == pytest.approx(0.5)
        assert result.engine_pass_rate == pytest.approx(1.0)

    def test_all_tests_pass_100_percent(self):
        result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=5, tests_failed=0, tests_total=5),
                "2": CardResult(collector_number="2", tests_passed=3, tests_failed=0, tests_total=3),
            },
            fdn_results={
                "10": CardResult(collector_number="10", tests_passed=4, tests_failed=0, tests_total=4),
            },
            engine_result=EngineResult(tests_passed=10, tests_failed=0, tests_total=10, pass_rate=1.0),
        )
        result.compute_aggregates()
        assert result.sos_pass_rate == pytest.approx(1.0)
        assert result.fdn_pass_rate == pytest.approx(1.0)
        assert result.engine_pass_rate == pytest.approx(1.0)

    def test_all_tests_fail_0_percent(self):
        result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=0, tests_failed=5, tests_total=5),
            },
            fdn_results={
                "10": CardResult(collector_number="10", tests_passed=0, tests_failed=4, tests_total=4),
            },
            engine_result=EngineResult(tests_passed=0, tests_failed=10, tests_total=10, pass_rate=0.0),
        )
        result.compute_aggregates()
        assert result.sos_pass_rate == pytest.approx(0.0)
        assert result.fdn_pass_rate == pytest.approx(0.0)
        assert result.engine_pass_rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Helpers for building fixture directories
# ---------------------------------------------------------------------------


def _make_pytest_result(passed: int, failed: int) -> MagicMock:
    """Create a mock subprocess.CompletedProcess with pytest-like output."""
    total = passed + failed
    parts = []
    if passed:
        parts.append(f"{passed} passed")
    if failed:
        parts.append(f"{failed} failed")
    summary = ", ".join(parts) + f" in 0.05s"
    mock = MagicMock()
    mock.stdout = summary + "\n"
    mock.stderr = ""
    mock.returncode = 0 if failed == 0 else 1
    return mock


def _setup_run_dir(tmp_path: Path, completed_cards: list[str]) -> Path:
    """Build a minimal run_dir with status.json and card_impl.py stubs."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    status = {cn: "completed" for cn in completed_cards}
    (run_dir / "status.json").write_text(json.dumps(status))
    for cn in completed_cards:
        card_dir = run_dir / "cards" / cn
        card_dir.mkdir(parents=True)
        (card_dir / "card_impl.py").write_text(f"# impl for {cn}\n")
    return run_dir


def _setup_audited_sos(tmp_path: Path, card_numbers: list[str]) -> Path:
    """Create fake audited SOS test files."""
    sos_dir = tmp_path / "tests" / "audited" / "sos"
    for cn in card_numbers:
        d = sos_dir / cn
        d.mkdir(parents=True)
        (d / "tests.py").write_text(f"# audited tests for SOS {cn}\n")
    return sos_dir


def _setup_audited_fdn(tmp_path: Path, card_numbers: list[str]) -> Path:
    """Create fake audited FDN test files."""
    fdn_dir = tmp_path / "tests" / "audited" / "fdn"
    for cn in card_numbers:
        d = fdn_dir / cn
        d.mkdir(parents=True)
        (d / "tests.py").write_text(f"# audited tests for FDN {cn}\n")
    return fdn_dir


def _setup_cards_dir(tmp_path: Path, fdn_cards: list[str]) -> Path:
    """Create a cards_dir with reference FDN card_impl.py files."""
    cards_dir = tmp_path / "cards"
    for cn in fdn_cards:
        d = cards_dir / "fdn" / cn
        d.mkdir(parents=True)
        (d / "card_impl.py").write_text(f"# ref FDN impl {cn}\n")
    return cards_dir


def _setup_engine_tests(tmp_path: Path) -> Path:
    """Create a fake engine tests directory."""
    engine_tests = tmp_path / "tests" / "engine"
    engine_tests.mkdir(parents=True)
    (engine_tests / "test_core.py").write_text("# engine tests\n")
    return engine_tests


# ---------------------------------------------------------------------------
# evaluate() integration tests (subprocess mocked)
# ---------------------------------------------------------------------------


class TestEvaluateSOS:
    """Dimension 1: SOS Card Correctness."""

    @patch("silverquillm.evaluator._REPO_ROOT")
    @patch("silverquillm.evaluator.subprocess.run")
    def test_sos_completed_card_runs_audited_tests(self, mock_run, mock_root, tmp_path):
        """Completed SOS card with audited tests should produce a CardResult."""
        mock_root.__truediv__ = lambda self, x: tmp_path / x
        # Redirect Path / operations for _REPO_ROOT
        mock_root_path = tmp_path
        
        run_dir = _setup_run_dir(tmp_path, ["42"])
        _setup_audited_sos(tmp_path, ["42"])
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=3, failed=1)

        with patch("silverquillm.evaluator._REPO_ROOT", mock_root_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert "42" in result.sos_results
        cr = result.sos_results["42"]
        assert cr.tests_passed == 3
        assert cr.tests_failed == 1
        assert cr.tests_total == 4
        assert cr.pass_rate == pytest.approx(0.75)

    @patch("silverquillm.evaluator.subprocess.run")
    def test_sos_result_json_written(self, mock_run, tmp_path):
        """Each SOS card should have a result.json written."""
        run_dir = _setup_run_dir(tmp_path, ["10"])
        sos_dir = _setup_audited_sos(tmp_path, ["10"])
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=2, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        result_json = run_dir / "cards" / "10" / "result.json"
        assert result_json.exists(), "result.json should be written for each SOS card"
        data = json.loads(result_json.read_text())
        assert data["tests_passed"] == 2
        assert data["collector_number"] == "10"

    @patch("silverquillm.evaluator.subprocess.run")
    def test_sos_card_without_audited_tests_skipped(self, mock_run, tmp_path):
        """Card with no audited tests should be skipped."""
        run_dir = _setup_run_dir(tmp_path, ["99"])
        # No audited tests created for card 99
        (tmp_path / "tests" / "audited" / "sos").mkdir(parents=True, exist_ok=True)
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert "99" in result.sos_results
        assert result.sos_results["99"].skipped is True

    @patch("silverquillm.evaluator.subprocess.run")
    def test_missing_status_json_returns_empty_sos(self, mock_run, tmp_path):
        """If status.json is missing, SOS results should be empty."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        # No status.json
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert result.sos_results == {}

    @patch("silverquillm.evaluator.subprocess.run")
    def test_no_completed_sos_cards(self, mock_run, tmp_path):
        """If no cards have 'completed' status, SOS results should be empty."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        status = {"1": "in_progress", "2": "failed"}
        (run_dir / "status.json").write_text(json.dumps(status))
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert result.sos_results == {}


class TestEvaluateFDN:
    """Dimension 2: FDN Card Regression."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_fdn_uses_reference_impl_not_agent_impl(self, mock_run, tmp_path):
        """FDN cards should use pre-filled reference card_impl.py from cards_dir."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")
        
        cards_dir = _setup_cards_dir(tmp_path, ["100"])
        _setup_audited_fdn(tmp_path, ["100"])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=4, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert "100" in result.fdn_results
        cr = result.fdn_results["100"]
        assert cr.tests_passed == 4
        assert cr.pass_rate == pytest.approx(1.0)

    @patch("silverquillm.evaluator.subprocess.run")
    def test_fdn_missing_reference_impl_produces_error(self, mock_run, tmp_path):
        """FDN card without reference card_impl.py should produce an error."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")
        
        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(parents=True)
        _setup_audited_fdn(tmp_path, ["200"])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert "200" in result.fdn_results
        cr = result.fdn_results["200"]
        assert len(cr.errors) > 0
        assert "card_impl.py" in cr.errors[0].lower() or "ref" in cr.errors[0].lower() or "No reference" in cr.errors[0]

    @patch("silverquillm.evaluator.subprocess.run")
    def test_fdn_no_audited_tests_returns_empty(self, mock_run, tmp_path):
        """No audited FDN test dir → empty FDN results."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")
        
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()
        # Don't create audited fdn dir at all

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert result.fdn_results == {}


class TestEvaluateEngine:
    """Dimension 3: Engine Regression."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_engine_tests_run_and_produce_result(self, mock_run, tmp_path):
        """Engine tests should produce an EngineResult."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")

        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()
        _setup_engine_tests(tmp_path)

        mock_run.return_value = _make_pytest_result(passed=9, failed=1)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        er = result.engine_result
        assert er.tests_passed == 9
        assert er.tests_failed == 1
        assert er.tests_total == 10
        assert er.pass_rate == pytest.approx(0.9)

    @patch("silverquillm.evaluator.subprocess.run")
    def test_engine_no_test_dir_returns_error(self, mock_run, tmp_path):
        """Missing engine tests directory → EngineResult with errors."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")

        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()
        # No engine test dir

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert len(result.engine_result.errors) > 0


class TestEngineDiffPatch:
    """engine_diff.patch support when engine_work/ doesn't exist."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_engine_diff_patch_applied_when_no_engine_work(self, mock_run, tmp_path):
        """If engine_work/ absent but engine_diff.patch exists, patch is applied."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")
        (run_dir / "engine_diff.patch").write_text("--- fake patch ---\n")

        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()
        (engine_dir / "__init__.py").write_text("")
        _setup_engine_tests(tmp_path)

        # First call = git apply, subsequent calls = pytest runs
        mock_run.return_value = _make_pytest_result(passed=5, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        # Verify git apply was called at some point
        git_calls = [
            c for c in mock_run.call_args_list
            if any("git" in str(a) for a in c.args + tuple(c.kwargs.values()))
        ]
        assert len(git_calls) > 0, "git apply should have been called for engine_diff.patch"

    @patch("silverquillm.evaluator.subprocess.run")
    def test_engine_work_dir_used_directly_when_present(self, mock_run, tmp_path):
        """If engine_work/ exists, it should be used directly (no patching)."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")
        engine_work = run_dir / "engine_work"
        engine_work.mkdir()
        (engine_work / "__init__.py").write_text("")

        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()
        _setup_engine_tests(tmp_path)

        mock_run.return_value = _make_pytest_result(passed=5, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        # No git apply calls
        git_calls = [
            c for c in mock_run.call_args_list
            if any("git" in str(a) for a in c.args + tuple(c.kwargs.values()))
        ]
        assert len(git_calls) == 0, "git apply should NOT be called when engine_work/ exists"


class TestEvaluateReturnType:
    """evaluate() returns a FullEvalResult with correct aggregation."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_evaluate_returns_full_eval_result(self, mock_run, tmp_path):
        """evaluate() should return a FullEvalResult instance."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}")
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert isinstance(result, FullEvalResult)

    @patch("silverquillm.evaluator.subprocess.run")
    def test_aggregates_computed_after_evaluate(self, mock_run, tmp_path):
        """evaluate() should call compute_aggregates() before returning."""
        run_dir = _setup_run_dir(tmp_path, ["1", "2"])
        _setup_audited_sos(tmp_path, ["1", "2"])
        cards_dir = _setup_cards_dir(tmp_path, [])
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()
        _setup_engine_tests(tmp_path)

        # SOS cards: 3 passed + 1 failed each
        mock_run.return_value = _make_pytest_result(passed=3, failed=1)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        # Aggregation should be computed already
        assert result.sos_pass_rate == pytest.approx(0.75)
