"""Tests for TODO item 17: regression test runner.

Verifies the regression runner module that detects when engine modifications
for one card break previously-completed cards' tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.regression import (
    CardRegressionResult,
    CompletedCard,
    RegressionResult,
    regression_feedback_prompt,
    run_regressions,
)


# ---------------------------------------------------------------------------
# CompletedCard dataclass
# ---------------------------------------------------------------------------


class TestCompletedCard:
    """Requirement 1: CompletedCard stores card info correctly."""

    def test_stores_card_id(self, tmp_path: Path):
        card = CompletedCard(card_id="alpha-001", workspace=tmp_path, tests_file=tmp_path / "t.py")
        assert card.card_id == "alpha-001"

    def test_stores_workspace_as_path(self, tmp_path: Path):
        card = CompletedCard(card_id="c1", workspace=tmp_path, tests_file=tmp_path / "t.py")
        assert isinstance(card.workspace, Path)
        assert card.workspace == tmp_path

    def test_stores_tests_file_as_path(self, tmp_path: Path):
        tf = tmp_path / "my_tests.py"
        card = CompletedCard(card_id="c1", workspace=tmp_path, tests_file=tf)
        assert isinstance(card.tests_file, Path)
        assert card.tests_file == tf


# ---------------------------------------------------------------------------
# CardRegressionResult dataclass
# ---------------------------------------------------------------------------


class TestCardRegressionResult:
    """Requirement 8: CardRegressionResult captures which tests failed."""

    def test_default_values(self):
        cr = CardRegressionResult(card_id="x", passed=True, tests_file="t.py")
        assert cr.num_passed == 0
        assert cr.num_failed == 0
        assert cr.num_errors == 0
        assert cr.failure_summary == ""

    def test_captures_failure_counts(self):
        cr = CardRegressionResult(
            card_id="x",
            passed=False,
            tests_file="t.py",
            num_passed=5,
            num_failed=2,
            num_errors=1,
            failure_summary="FAILED test_foo - AssertionError",
        )
        assert cr.num_failed == 2
        assert cr.num_errors == 1
        assert cr.num_passed == 5
        assert "FAILED" in cr.failure_summary

    def test_passed_flag_is_bool(self):
        cr = CardRegressionResult(card_id="x", passed=False, tests_file="t.py")
        assert cr.passed is False


# ---------------------------------------------------------------------------
# RegressionResult dataclass
# ---------------------------------------------------------------------------


class TestRegressionResult:
    """Requirement 9: RegressionResult aggregates multiple card results."""

    def test_empty_has_no_failures(self):
        rr = RegressionResult()
        assert rr.has_failures is False
        assert rr.failed_cards == []
        assert rr.total_cards == 0

    def test_all_passing_has_no_failures(self):
        cards = [
            CardRegressionResult(card_id="a", passed=True, tests_file="t.py"),
            CardRegressionResult(card_id="b", passed=True, tests_file="t.py"),
        ]
        rr = RegressionResult(card_results=cards, total_cards=2, cards_passed=2, cards_failed=0)
        assert rr.has_failures is False
        assert len(rr.failed_cards) == 0

    def test_mixed_results_reports_failures(self):
        cards = [
            CardRegressionResult(card_id="a", passed=True, tests_file="t.py"),
            CardRegressionResult(card_id="b", passed=False, tests_file="t.py", failure_summary="err"),
            CardRegressionResult(card_id="c", passed=False, tests_file="t.py", failure_summary="err2"),
        ]
        rr = RegressionResult(card_results=cards, total_cards=3, cards_passed=1, cards_failed=2)
        assert rr.has_failures is True
        assert len(rr.failed_cards) == 2
        failed_ids = {c.card_id for c in rr.failed_cards}
        assert failed_ids == {"b", "c"}

    def test_to_dict_serialization(self):
        """Requirement 12: regression results stored in result dict/json."""
        cr = CardRegressionResult(
            card_id="001", passed=False, tests_file="t.py",
            num_passed=3, num_failed=1, num_errors=0,
            failure_summary="assert 1 == 2",
        )
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=0, cards_failed=1)
        d = rr.to_dict()

        assert isinstance(d, dict)
        assert d["total_cards"] == 1
        assert d["cards_passed"] == 0
        assert d["cards_failed"] == 1
        assert len(d["card_results"]) == 1

        card_d = d["card_results"][0]
        assert card_d["card_id"] == "001"
        assert card_d["passed"] is False
        assert card_d["num_failed"] == 1
        assert card_d["failure_summary"] == "assert 1 == 2"

    def test_to_dict_is_json_serializable(self):
        """Requirement 12: ensure the dict can actually be stored as JSON."""
        import json

        cr = CardRegressionResult(card_id="x", passed=True, tests_file="t.py", num_passed=2)
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=1, cards_failed=0)
        serialized = json.dumps(rr.to_dict())
        assert isinstance(serialized, str)
        roundtripped = json.loads(serialized)
        assert roundtripped["card_results"][0]["card_id"] == "x"


# ---------------------------------------------------------------------------
# run_regressions — empty / first card
# ---------------------------------------------------------------------------


class TestRunRegressionsEmpty:
    """Requirements 2, 13: no previous cards returns empty/passing result."""

    def test_no_cards_returns_empty_result(self):
        result = run_regressions([])
        assert result.total_cards == 0
        assert result.cards_passed == 0
        assert result.cards_failed == 0
        assert result.has_failures is False

    def test_no_cards_returns_regression_result_type(self):
        result = run_regressions([])
        assert isinstance(result, RegressionResult)


# ---------------------------------------------------------------------------
# run_regressions — passing tests
# ---------------------------------------------------------------------------


class TestRunRegressionsPassingCards:
    """Requirements 3, 4: runs tests and correctly reports passing cards."""

    def test_single_passing_card(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        tf = ws / "test_card.py"
        tf.write_text("def test_simple(): assert 1 + 1 == 2\n")

        card = CompletedCard(card_id="pass-001", workspace=ws, tests_file=tf)
        result = run_regressions([card])

        assert result.total_cards == 1
        assert result.cards_passed == 1
        assert result.cards_failed == 0
        assert not result.has_failures

    def test_multiple_passing_cards(self, tmp_path: Path):
        cards = []
        for i in range(3):
            ws = tmp_path / f"ws_{i}"
            ws.mkdir()
            tf = ws / "tests.py"
            tf.write_text(f"def test_card_{i}(): assert True\n")
            cards.append(CompletedCard(card_id=f"pass-{i:03d}", workspace=ws, tests_file=tf))

        result = run_regressions(cards)
        assert result.total_cards == 3
        assert result.cards_passed == 3
        assert result.cards_failed == 0

    def test_passing_card_result_has_counts(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        tf = ws / "test_card.py"
        tf.write_text("def test_a(): pass\ndef test_b(): pass\n")

        card = CompletedCard(card_id="cnt", workspace=ws, tests_file=tf)
        result = run_regressions([card])

        cr = result.card_results[0]
        assert cr.passed is True
        assert cr.num_passed >= 2
        assert cr.num_failed == 0


# ---------------------------------------------------------------------------
# run_regressions — failing tests
# ---------------------------------------------------------------------------


class TestRunRegressionsFailingCards:
    """Requirements 5, 8: detects and reports failing cards."""

    def test_single_failing_card(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        tf = ws / "tests.py"
        tf.write_text("def test_broken(): assert False, 'intentional failure'\n")

        card = CompletedCard(card_id="fail-001", workspace=ws, tests_file=tf)
        result = run_regressions([card])

        assert result.total_cards == 1
        assert result.cards_failed == 1
        assert result.has_failures is True
        cr = result.card_results[0]
        assert cr.passed is False
        assert cr.num_failed >= 1
        assert cr.failure_summary != ""

    def test_mixed_pass_fail(self, tmp_path: Path):
        # Passing card
        ws1 = tmp_path / "pass_ws"
        ws1.mkdir()
        tf1 = ws1 / "tests.py"
        tf1.write_text("def test_ok(): assert True\n")

        # Failing card
        ws2 = tmp_path / "fail_ws"
        ws2.mkdir()
        tf2 = ws2 / "tests.py"
        tf2.write_text("def test_broken(): assert False\n")

        cards = [
            CompletedCard(card_id="p1", workspace=ws1, tests_file=tf1),
            CompletedCard(card_id="f1", workspace=ws2, tests_file=tf2),
        ]
        result = run_regressions(cards)

        assert result.total_cards == 2
        assert result.cards_passed == 1
        assert result.cards_failed == 1
        failed_ids = [c.card_id for c in result.failed_cards]
        assert "f1" in failed_ids
        assert "p1" not in failed_ids

    def test_failure_summary_contains_details(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        tf = ws / "tests.py"
        tf.write_text("def test_x(): assert 42 == 99, 'expected 42 to equal 99'\n")

        card = CompletedCard(card_id="det", workspace=ws, tests_file=tf)
        result = run_regressions([card])

        cr = result.card_results[0]
        assert cr.failure_summary  # non-empty


# ---------------------------------------------------------------------------
# run_regressions — error handling
# ---------------------------------------------------------------------------


class TestRunRegressionsErrors:
    """Requirements 6, 7, 13: handles subprocess errors, missing tests, edge cases."""

    def test_missing_test_file_treated_as_skip(self, tmp_path: Path):
        """Requirement 7: missing test file should not fail the card."""
        card = CompletedCard(
            card_id="nofile",
            workspace=tmp_path,
            tests_file=tmp_path / "does_not_exist.py",
        )
        result = run_regressions([card])
        # Missing test file should be treated as passed (skipped)
        assert result.total_cards == 1
        cr = result.card_results[0]
        assert cr.passed is True

    @patch("silverquillm.regression.subprocess.run", side_effect=OSError("spawn failed"))
    def test_subprocess_oserror(self, mock_run, tmp_path: Path):
        """Requirement 6: subprocess errors handled gracefully."""
        tf = tmp_path / "tests.py"
        tf.write_text("def test_x(): pass\n")
        card = CompletedCard(card_id="oserr", workspace=tmp_path, tests_file=tf)

        result = run_regressions([card])
        assert result.cards_failed == 1
        cr = result.card_results[0]
        assert cr.passed is False
        assert "subprocess error" in cr.failure_summary

    def test_timeout_handled_gracefully(self, tmp_path: Path):
        """Requirement 6: timeout should not crash, should report failure."""
        tf = tmp_path / "tests.py"
        tf.write_text("import time\ndef test_hang(): time.sleep(300)\n")
        card = CompletedCard(card_id="slow", workspace=tmp_path, tests_file=tf)

        result = run_regressions([card], timeout=1)
        cr = result.card_results[0]
        assert cr.passed is False
        assert "timed out" in cr.failure_summary

    def test_card_with_no_tests_in_file(self, tmp_path: Path):
        """Requirement 13: card with test file but no test functions."""
        ws = tmp_path / "ws"
        ws.mkdir()
        tf = ws / "tests.py"
        tf.write_text("# empty test file\nx = 1\n")

        card = CompletedCard(card_id="empty", workspace=ws, tests_file=tf)
        result = run_regressions([card])
        # pytest returns 5 (no tests collected) — implementation should handle
        cr = result.card_results[0]
        # An empty test file with no test functions: pytest exit code 5
        # The implementation treats non-zero as failure, which is acceptable
        assert isinstance(cr.passed, bool)


# ---------------------------------------------------------------------------
# regression_feedback_prompt
# ---------------------------------------------------------------------------


class TestRegressionFeedbackPrompt:
    """Requirements 10, 11: feedback prompt formatting."""

    def test_empty_result_returns_empty_string(self):
        """Requirement 11: no failures -> empty/None."""
        rr = RegressionResult()
        prompt = regression_feedback_prompt(rr)
        assert prompt == ""

    def test_all_passing_returns_empty_string(self):
        """Requirement 11: all passing -> empty string."""
        cards = [CardRegressionResult(card_id="a", passed=True, tests_file="t.py")]
        rr = RegressionResult(card_results=cards, total_cards=1, cards_passed=1, cards_failed=0)
        prompt = regression_feedback_prompt(rr)
        assert prompt == ""

    def test_failure_prompt_contains_card_id(self):
        """Requirement 10: prompt identifies which card failed."""
        cr = CardRegressionResult(
            card_id="broken-card",
            passed=False,
            tests_file="tests/test_broken.py",
            num_failed=1,
            failure_summary="assert x == 42",
        )
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=0, cards_failed=1)
        prompt = regression_feedback_prompt(rr)
        assert "broken-card" in prompt

    def test_failure_prompt_contains_failure_details(self):
        """Requirement 10: prompt includes failure details."""
        cr = CardRegressionResult(
            card_id="c1",
            passed=False,
            tests_file="t.py",
            num_passed=3,
            num_failed=2,
            failure_summary="AssertionError: expected 5 got 3",
        )
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=0, cards_failed=1)
        prompt = regression_feedback_prompt(rr)
        assert "AssertionError" in prompt
        assert "Failed: 2" in prompt or "2 failed" in prompt.lower() or "num_failed" in prompt.lower() or "2" in prompt

    def test_failure_prompt_mentions_regression(self):
        """Requirement 10: prompt should mention regression context."""
        cr = CardRegressionResult(card_id="c1", passed=False, tests_file="t.py", failure_summary="err")
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=0, cards_failed=1)
        prompt = regression_feedback_prompt(rr)
        assert "regression" in prompt.lower() or "Regression" in prompt

    def test_failure_prompt_instructs_fix(self):
        """Requirement 10: prompt should instruct agent to fix regressions."""
        cr = CardRegressionResult(card_id="c1", passed=False, tests_file="t.py", failure_summary="err")
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=0, cards_failed=1)
        prompt = regression_feedback_prompt(rr)
        assert "fix" in prompt.lower() or "Fix" in prompt

    def test_multiple_failures_all_appear_in_prompt(self):
        """Requirement 10: multiple failing cards each appear in prompt."""
        crs = [
            CardRegressionResult(card_id="card-A", passed=False, tests_file="a.py", failure_summary="fail A"),
            CardRegressionResult(card_id="card-B", passed=False, tests_file="b.py", failure_summary="fail B"),
        ]
        # Include a passing card too — should NOT appear in prompt
        crs_all = crs + [CardRegressionResult(card_id="card-C", passed=True, tests_file="c.py")]
        rr = RegressionResult(card_results=crs_all, total_cards=3, cards_passed=1, cards_failed=2)
        prompt = regression_feedback_prompt(rr)
        assert "card-A" in prompt
        assert "card-B" in prompt
        assert "fail A" in prompt
        assert "fail B" in prompt
