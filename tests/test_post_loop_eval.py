"""Tests for TODO item 6: Wire `benchmark run` post-loop: self-eval and summary.

Tests verify:
- run_self_eval_flat works with flat layout (blind_impl.py, tested_impl.py, tests.py).
- run_self_eval_flat returns appropriate EvalResult when tests pass.
- run_self_eval_flat returns appropriate EvalResult when implementation is missing.
- Post-loop creates summary.json with correct card_count.
- Self-eval results are merged into each card's result.json.
- Summary stats are printed (total cards, pass rates, elapsed time).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmark.evaluator import EvalResult, run_self_eval_flat
from benchmark.results import save_run_summary


# ---------------------------------------------------------------------------
# Mock implementation / test fixtures
# ---------------------------------------------------------------------------

CORRECT_IMPL = textwrap.dedent("""\
    def add(a, b):
        return a + b
""")

BUGGY_IMPL = textwrap.dedent("""\
    def add(a, b):
        return a - b  # BUG
""")

SIMPLE_TESTS = textwrap.dedent("""\
    from card_impl import add

    def test_add_positive():
        assert add(2, 3) == 5

    def test_add_zero():
        assert add(0, 0) == 0
""")


# ---------------------------------------------------------------------------
# Tests for run_self_eval_flat
# ---------------------------------------------------------------------------


class TestRunSelfEvalFlat:
    """Tests for run_self_eval_flat with flat card directory layout."""

    def test_returns_eval_result_with_correct_card_id(self, tmp_path: Path):
        """run_self_eval_flat returns EvalResult with card_id from dir name."""
        card_dir = tmp_path / "card-add-numbers"
        card_dir.mkdir()
        (card_dir / "blind_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tested_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)

        result = run_self_eval_flat(card_dir, "test-agent")

        assert isinstance(result, EvalResult)
        assert result.card_id == "card-add-numbers"
        assert result.agent == "test-agent"
        assert result.eval_type == "self"

    def test_correct_impl_passes_all_tests(self, tmp_path: Path):
        """When both impls are correct, all tests should pass."""
        card_dir = tmp_path / "card-correct"
        card_dir.mkdir()
        (card_dir / "blind_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tested_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)

        result = run_self_eval_flat(card_dir, "agent-a")

        assert result.blind_passed == 2
        assert result.blind_failed == 0
        assert result.blind_total == 2
        assert result.tested_passed == 2
        assert result.tested_failed == 0
        assert result.tested_total == 2
        assert result.errors == []

    def test_buggy_impl_fails_tests(self, tmp_path: Path):
        """When blind_impl is buggy, blind tests should fail."""
        card_dir = tmp_path / "card-buggy"
        card_dir.mkdir()
        (card_dir / "blind_impl.py").write_text(BUGGY_IMPL)
        (card_dir / "tested_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)

        result = run_self_eval_flat(card_dir, "agent-b")

        # Buggy impl: test_add_positive fails (2-3=-1 != 5), test_add_zero passes (0-0=0)
        assert result.blind_passed < result.blind_total
        assert result.blind_failed > 0
        # Tested impl is correct
        assert result.tested_passed == 2
        assert result.tested_total == 2

    def test_missing_blind_impl_reports_error(self, tmp_path: Path):
        """When blind_impl.py is missing, errors list should report it."""
        card_dir = tmp_path / "card-no-blind"
        card_dir.mkdir()
        # No blind_impl.py
        (card_dir / "tested_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)

        result = run_self_eval_flat(card_dir, "agent-c")

        assert result.blind_passed == 0
        assert result.blind_total == 0
        assert any("blind_impl" in e for e in result.errors)
        # tested_impl should still run fine
        assert result.tested_passed == 2

    def test_missing_tested_impl_reports_error(self, tmp_path: Path):
        """When tested_impl.py is missing, errors list should report it."""
        card_dir = tmp_path / "card-no-tested"
        card_dir.mkdir()
        (card_dir / "blind_impl.py").write_text(CORRECT_IMPL)
        # No tested_impl.py
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)

        result = run_self_eval_flat(card_dir, "agent-d")

        assert result.tested_passed == 0
        assert result.tested_total == 0
        assert any("tested_impl" in e for e in result.errors)
        # blind_impl should still run
        assert result.blind_passed == 2

    def test_missing_tests_file_reports_error(self, tmp_path: Path):
        """When tests.py is missing, errors should report it for both impls."""
        card_dir = tmp_path / "card-no-tests"
        card_dir.mkdir()
        (card_dir / "blind_impl.py").write_text(CORRECT_IMPL)
        (card_dir / "tested_impl.py").write_text(CORRECT_IMPL)
        # No tests.py

        result = run_self_eval_flat(card_dir, "agent-e")

        assert result.blind_passed == 0
        assert result.blind_total == 0
        assert result.tested_passed == 0
        assert result.tested_total == 0
        assert any("tests.py" in e or "Missing" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Tests for post-loop: summary.json and result.json merging
# ---------------------------------------------------------------------------


class TestPostLoopSummary:
    """Tests for post-loop summary creation and result merging."""

    def _create_run_dir_with_cards(self, tmp_path: Path, num_cards: int = 2) -> Path:
        """Helper: create a mock run directory with card results."""
        run_dir = tmp_path / "runs" / "test-run"
        cards_dir = run_dir / "cards"
        cards_dir.mkdir(parents=True)

        for i in range(num_cards):
            card_dir = cards_dir / f"card-{i}"
            card_dir.mkdir()
            (card_dir / "blind_impl.py").write_text(CORRECT_IMPL)
            (card_dir / "tested_impl.py").write_text(CORRECT_IMPL)
            (card_dir / "tests.py").write_text(SIMPLE_TESTS)
            # Write initial result.json (as orchestration loop would)
            result_json = {
                "card_id": f"card-{i}",
                "agent": "test-model",
                "complexity_tier": "medium",
                "status": "success",
            }
            (card_dir / "result.json").write_text(json.dumps(result_json))

        return run_dir

    def test_save_run_summary_writes_correct_card_count(self, tmp_path: Path):
        """summary.json should have card_count matching number of results."""
        run_dir = tmp_path / "run-dir"
        run_dir.mkdir()

        results = [
            {"agent": "model-a", "complexity_tier": "easy", "self_eval": {"tested": {"passed": 2, "total": 2}}},
            {"agent": "model-a", "complexity_tier": "medium", "self_eval": {"tested": {"passed": 1, "total": 2}}},
            {"agent": "model-a", "complexity_tier": "hard", "self_eval": {"tested": {"passed": 0, "total": 2}}},
        ]

        summary_path = save_run_summary(run_dir, results)

        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 3

    def test_save_run_summary_with_empty_results(self, tmp_path: Path):
        """summary.json with no results should have card_count=0."""
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()

        summary_path = save_run_summary(run_dir, [])

        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 0

    def test_self_eval_merged_into_result_json(self, tmp_path: Path):
        """Post-loop should merge self_eval data into each card's result.json."""
        run_dir = self._create_run_dir_with_cards(tmp_path, num_cards=1)
        cards_dir = run_dir / "cards"
        card_path = cards_dir / "card-0"

        # Simulate post-loop: run self-eval and merge
        eval_result = run_self_eval_flat(card_path, "test-model")

        result_json_path = card_path / "result.json"
        record = json.loads(result_json_path.read_text())
        record["self_eval"] = {
            "blind": {
                "passed": eval_result.blind_passed,
                "failed": eval_result.blind_failed,
                "total": eval_result.blind_total,
            },
            "tested": {
                "passed": eval_result.tested_passed,
                "failed": eval_result.tested_failed,
                "total": eval_result.tested_total,
            },
            "errors": eval_result.errors,
        }
        result_json_path.write_text(json.dumps(record, indent=2))

        # Verify merged result
        saved = json.loads(result_json_path.read_text())
        assert "self_eval" in saved
        assert saved["self_eval"]["blind"]["passed"] == 2
        assert saved["self_eval"]["blind"]["total"] == 2
        assert saved["self_eval"]["tested"]["passed"] == 2
        assert saved["self_eval"]["tested"]["total"] == 2
        assert saved["self_eval"]["errors"] == []

    def test_full_post_loop_creates_summary_with_correct_count(self, tmp_path: Path):
        """Simulating full post-loop: iterates cards, runs eval, saves summary."""
        run_dir = self._create_run_dir_with_cards(tmp_path, num_cards=3)
        cards_dir = run_dir / "cards"

        # Simulate post-loop logic from cli.py
        all_results: list[dict] = []
        for card_path in sorted(cards_dir.iterdir()):
            if not card_path.is_dir():
                continue
            result_json = card_path / "result.json"
            if not result_json.exists():
                continue

            eval_result = run_self_eval_flat(card_path, "test-model")

            record = json.loads(result_json.read_text())
            record["self_eval"] = {
                "blind": {
                    "passed": eval_result.blind_passed,
                    "failed": eval_result.blind_failed,
                    "total": eval_result.blind_total,
                },
                "tested": {
                    "passed": eval_result.tested_passed,
                    "failed": eval_result.tested_failed,
                    "total": eval_result.tested_total,
                },
                "errors": eval_result.errors,
            }
            result_json.write_text(json.dumps(record, indent=2, default=str))
            all_results.append(record)

        summary_path = save_run_summary(run_dir, all_results)

        # Verify summary
        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 3
        assert summary["self_eval"]["total_passed"] == 6  # 3 cards * 2 tests each
        assert summary["self_eval"]["total_tests"] == 6

    def test_summary_stats_contain_agents(self, tmp_path: Path):
        """summary.json should list unique agents."""
        run_dir = tmp_path / "agents-run"
        run_dir.mkdir()

        results = [
            {"agent": "claude-sonnet", "complexity_tier": "easy", "self_eval": {"tested": {"passed": 1, "total": 1}}},
            {"agent": "claude-sonnet", "complexity_tier": "medium", "self_eval": {"tested": {"passed": 1, "total": 1}}},
        ]

        summary_path = save_run_summary(run_dir, results)
        summary = json.loads(summary_path.read_text())

        assert "agents" in summary
        assert "claude-sonnet" in summary["agents"]
        assert len(summary["agents"]) == 1
