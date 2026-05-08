"""Tests for TODO item 17: regression test runner.

Validates the regression runner module that re-runs previously-completed
cards' tests after each card's test-informed phase to detect regressions.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from silverquillm.regression import (
    CardRegressionResult,
    CompletedCard,
    RegressionResult,
    _parse_pytest_summary,
    _run_card_tests,
    regression_feedback_prompt,
    run_regressions,
)


# ---------------------------------------------------------------------------
# CardRegressionResult dataclass
# ---------------------------------------------------------------------------

class TestCardRegressionResult:
    def test_defaults(self):
        cr = CardRegressionResult(card_id="001", passed=True, tests_file="tests.py")
        assert cr.card_id == "001"
        assert cr.passed is True
        assert cr.num_passed == 0
        assert cr.num_failed == 0
        assert cr.num_errors == 0
        assert cr.failure_summary == ""

    def test_with_failures(self):
        cr = CardRegressionResult(
            card_id="002",
            passed=False,
            tests_file="tests.py",
            num_passed=3,
            num_failed=2,
            num_errors=1,
            failure_summary="test_foo FAILED",
        )
        assert cr.passed is False
        assert cr.num_failed == 2
        assert cr.failure_summary == "test_foo FAILED"


# ---------------------------------------------------------------------------
# RegressionResult dataclass
# ---------------------------------------------------------------------------

class TestRegressionResult:
    def test_empty_result(self):
        rr = RegressionResult()
        assert rr.total_cards == 0
        assert rr.cards_passed == 0
        assert rr.cards_failed == 0
        assert rr.has_failures is False
        assert rr.failed_cards == []

    def test_all_passing(self):
        cards = [
            CardRegressionResult(card_id="001", passed=True, tests_file="t.py"),
            CardRegressionResult(card_id="002", passed=True, tests_file="t.py"),
        ]
        rr = RegressionResult(card_results=cards, total_cards=2, cards_passed=2, cards_failed=0)
        assert rr.has_failures is False
        assert rr.failed_cards == []

    def test_some_failing(self):
        cards = [
            CardRegressionResult(card_id="001", passed=True, tests_file="t.py"),
            CardRegressionResult(card_id="002", passed=False, tests_file="t.py", failure_summary="boom"),
        ]
        rr = RegressionResult(card_results=cards, total_cards=2, cards_passed=1, cards_failed=1)
        assert rr.has_failures is True
        assert len(rr.failed_cards) == 1
        assert rr.failed_cards[0].card_id == "002"

    def test_to_dict(self):
        cr = CardRegressionResult(card_id="001", passed=True, tests_file="t.py", num_passed=5)
        rr = RegressionResult(card_results=[cr], total_cards=1, cards_passed=1, cards_failed=0)
        d = rr.to_dict()
        assert d["total_cards"] == 1
        assert d["cards_passed"] == 1
        assert d["cards_failed"] == 0
        assert len(d["card_results"]) == 1
        assert d["card_results"][0]["card_id"] == "001"
        assert d["card_results"][0]["passed"] is True
        assert d["card_results"][0]["num_passed"] == 5


# ---------------------------------------------------------------------------
# _parse_pytest_summary
# ---------------------------------------------------------------------------

class TestParsePytestSummary:
    def test_all_passed(self):
        stdout = "===== 5 passed in 0.12s ====="
        p, f, e = _parse_pytest_summary(stdout)
        assert p == 5
        assert f == 0
        assert e == 0

    def test_mixed(self):
        stdout = "===== 3 passed, 2 failed, 1 error in 1.5s ====="
        p, f, e = _parse_pytest_summary(stdout)
        assert p == 3
        assert f == 2
        assert e == 1

    def test_no_match(self):
        p, f, e = _parse_pytest_summary("some random output")
        assert p == 0
        assert f == 0
        assert e == 0


# ---------------------------------------------------------------------------
# _run_card_tests
# ---------------------------------------------------------------------------

class TestRunCardTests:
    def test_no_test_file(self, tmp_path):
        card = CompletedCard(
            card_id="001",
            workspace=tmp_path,
            tests_file=tmp_path / "nonexistent_tests.py",
        )
        result = _run_card_tests(card)
        assert result.passed is True
        assert "skipped" in result.failure_summary

    def test_passing_tests(self, tmp_path):
        tests = tmp_path / "tests.py"
        tests.write_text("def test_ok(): assert True\n")
        card = CompletedCard(card_id="001", workspace=tmp_path, tests_file=tests)

        result = _run_card_tests(card)
        assert result.passed is True
        assert result.num_passed >= 1
        assert result.num_failed == 0

    def test_failing_tests(self, tmp_path):
        tests = tmp_path / "tests.py"
        tests.write_text("def test_fail(): assert False\n")
        card = CompletedCard(card_id="002", workspace=tmp_path, tests_file=tests)

        result = _run_card_tests(card)
        assert result.passed is False
        assert result.num_failed >= 1
        assert result.failure_summary != ""

    def test_timeout(self, tmp_path):
        tests = tmp_path / "tests.py"
        tests.write_text("import time\ndef test_slow(): time.sleep(100)\n")
        card = CompletedCard(card_id="003", workspace=tmp_path, tests_file=tests)

        result = _run_card_tests(card, timeout=1)
        assert result.passed is False
        assert "timed out" in result.failure_summary

    @patch("silverquillm.regression.subprocess.run", side_effect=OSError("no pytest"))
    def test_subprocess_error(self, mock_run, tmp_path):
        tests = tmp_path / "tests.py"
        tests.write_text("def test_ok(): pass\n")
        card = CompletedCard(card_id="004", workspace=tmp_path, tests_file=tests)

        result = _run_card_tests(card)
        assert result.passed is False
        assert "subprocess error" in result.failure_summary


# ---------------------------------------------------------------------------
# run_regressions
# ---------------------------------------------------------------------------

class TestRunRegressions:
    def test_empty_list(self):
        result = run_regressions([])
        assert result.total_cards == 0
        assert result.has_failures is False

    def test_all_passing(self, tmp_path):
        cards = []
        for i in range(3):
            ws = tmp_path / f"card_{i}"
            ws.mkdir()
            tests = ws / "tests.py"
            tests.write_text(f"def test_card_{i}(): assert True\n")
            cards.append(CompletedCard(card_id=f"00{i}", workspace=ws, tests_file=tests))

        result = run_regressions(cards)
        assert result.total_cards == 3
        assert result.cards_passed == 3
        assert result.cards_failed == 0
        assert result.has_failures is False

    def test_mixed_results(self, tmp_path):
        ws1 = tmp_path / "card_pass"
        ws1.mkdir()
        t1 = ws1 / "tests.py"
        t1.write_text("def test_ok(): assert True\n")

        ws2 = tmp_path / "card_fail"
        ws2.mkdir()
        t2 = ws2 / "tests.py"
        t2.write_text("def test_fail(): assert False\n")

        cards = [
            CompletedCard(card_id="001", workspace=ws1, tests_file=t1),
            CompletedCard(card_id="002", workspace=ws2, tests_file=t2),
        ]
        result = run_regressions(cards)
        assert result.total_cards == 2
        assert result.cards_passed == 1
        assert result.cards_failed == 1
        assert result.has_failures is True

    def test_first_card_no_previous(self):
        """First card in run — no previous cards to check."""
        result = run_regressions([])
        assert result.total_cards == 0
        assert not result.has_failures


# ---------------------------------------------------------------------------
# regression_feedback_prompt
# ---------------------------------------------------------------------------

class TestRegressionFeedbackPrompt:
    def test_no_failures(self):
        rr = RegressionResult()
        assert regression_feedback_prompt(rr) == ""

    def test_with_failures(self):
        cr = CardRegressionResult(
            card_id="001",
            passed=False,
            tests_file="tests.py",
            num_passed=3,
            num_failed=2,
            num_errors=0,
            failure_summary="assert x == 42",
        )
        rr = RegressionResult(
            card_results=[cr],
            total_cards=1,
            cards_passed=0,
            cards_failed=1,
        )
        prompt = regression_feedback_prompt(rr)
        assert "Regression" in prompt
        assert "Card 001" in prompt
        assert "assert x == 42" in prompt
        assert "Failed: 2" in prompt

    def test_multiple_failures(self):
        crs = [
            CardRegressionResult(card_id=f"00{i}", passed=False, tests_file="t.py",
                                 num_failed=i, failure_summary=f"fail {i}")
            for i in range(1, 4)
        ]
        rr = RegressionResult(
            card_results=crs,
            total_cards=3,
            cards_passed=0,
            cards_failed=3,
        )
        prompt = regression_feedback_prompt(rr)
        assert "Card 001" in prompt
        assert "Card 002" in prompt
        assert "Card 003" in prompt
