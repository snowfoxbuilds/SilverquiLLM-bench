"""Tests for TODO item 12: Evaluation runner.

Tests verify:
- EvalResult dataclass has all required fields with correct types.
- run_tests: copies impl as card_impl.py, runs pytest in subprocess, parses output.
- run_tests: timeout handling returns zeros and error message.
- run_tests: buggy impl returns failures, correct impl passes.
- run_self_eval: runs blind_impl.py and tested_impl.py against agent's tests.py.
- run_self_eval: handles missing files gracefully with error messages.
- run_cross_eval: produces N*(N-1) results for N agents.
- run_cross_eval: each result has correct eval_type with cross:test_agent format.
- run_audited_eval: runs all agents against gold-standard tests.
- Mock scenario: correct impl passes more tests than buggy impl.
- _parse_pytest_output: parses various pytest summary formats.
"""

from __future__ import annotations

import dataclasses
import textwrap
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from benchmark.evaluator import (
    EvalResult,
    _parse_pytest_output,
    run_audited_eval,
    run_cross_eval,
    run_self_eval,
    run_tests,
)


# ---------------------------------------------------------------------------
# Fixtures: create mock implementations and tests on disk
# ---------------------------------------------------------------------------

CORRECT_IMPL = textwrap.dedent("""\
    def add(a, b):
        return a + b

    def multiply(a, b):
        return a * b
""")

BUGGY_IMPL = textwrap.dedent("""\
    def add(a, b):
        return a - b  # BUG: subtracts instead

    def multiply(a, b):
        return a + b  # BUG: adds instead
""")

TESTS_CODE = textwrap.dedent("""\
    from card_impl import add, multiply

    def test_add_positive():
        assert add(2, 3) == 5

    def test_add_zero():
        assert add(0, 0) == 0

    def test_multiply_positive():
        assert multiply(2, 3) == 6

    def test_multiply_zero():
        assert multiply(5, 0) == 0
""")

SYNTAX_ERROR_IMPL = textwrap.dedent("""\
    def add(a, b)
        return a + b  # missing colon -> SyntaxError
""")

SLOW_IMPL = textwrap.dedent("""\
    import time

    def add(a, b):
        time.sleep(120)
        return a + b

    def multiply(a, b):
        return a * b
""")


@pytest.fixture()
def correct_impl_file(tmp_path: Path) -> Path:
    p = tmp_path / "correct_impl.py"
    p.write_text(CORRECT_IMPL)
    return p


@pytest.fixture()
def buggy_impl_file(tmp_path: Path) -> Path:
    p = tmp_path / "buggy_impl.py"
    p.write_text(BUGGY_IMPL)
    return p


@pytest.fixture()
def tests_file(tmp_path: Path) -> Path:
    p = tmp_path / "tests.py"
    p.write_text(TESTS_CODE)
    return p


@pytest.fixture()
def syntax_error_impl_file(tmp_path: Path) -> Path:
    p = tmp_path / "syntax_error_impl.py"
    p.write_text(SYNTAX_ERROR_IMPL)
    return p


@pytest.fixture()
def slow_impl_file(tmp_path: Path) -> Path:
    p = tmp_path / "slow_impl.py"
    p.write_text(SLOW_IMPL)
    return p


@pytest.fixture()
def card_dir(tmp_path: Path) -> Path:
    """Create a card directory with two agents: agent_a (correct) and agent_b (buggy)."""
    card = tmp_path / "test_card"

    for agent_name, impl_code in [("agent_a", CORRECT_IMPL), ("agent_b", BUGGY_IMPL)]:
        agent = card / agent_name
        agent.mkdir(parents=True)
        (agent / "blind_impl.py").write_text(impl_code)
        (agent / "tested_impl.py").write_text(impl_code)
        (agent / "tests.py").write_text(TESTS_CODE)

    return card


# ---------------------------------------------------------------------------
# EvalResult dataclass
# ---------------------------------------------------------------------------


class TestEvalResultDataclass:
    """Verify EvalResult has all required fields."""

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(EvalResult)

    def test_has_required_fields(self):
        field_names = {f.name for f in dc_fields(EvalResult)}
        expected = {
            "card_id",
            "agent",
            "eval_type",
            "blind_passed",
            "blind_failed",
            "blind_total",
            "tested_passed",
            "tested_failed",
            "tested_total",
            "errors",
        }
        assert expected <= field_names

    def test_errors_default_is_empty_list(self):
        result = EvalResult(
            card_id="c1",
            agent="a1",
            eval_type="self",
            blind_passed=0,
            blind_failed=0,
            blind_total=0,
            tested_passed=0,
            tested_failed=0,
            tested_total=0,
        )
        assert result.errors == []

    def test_errors_is_list_of_str(self):
        result = EvalResult(
            card_id="c1",
            agent="a1",
            eval_type="self",
            blind_passed=0,
            blind_failed=0,
            blind_total=0,
            tested_passed=0,
            tested_failed=0,
            tested_total=0,
            errors=["err1", "err2"],
        )
        assert isinstance(result.errors, list)
        assert all(isinstance(e, str) for e in result.errors)


# ---------------------------------------------------------------------------
# _parse_pytest_output (internal but critical parsing logic)
# ---------------------------------------------------------------------------


class TestParsePytestOutput:
    """Verify pytest output parsing extracts correct counts."""

    def test_all_passed(self):
        output = "4 passed in 0.05s\n"
        passed, failed, total, errors = _parse_pytest_output(output)
        assert passed == 4
        assert failed == 0
        assert total == 4

    def test_mixed_pass_fail(self):
        output = "3 passed, 2 failed in 0.10s\n"
        passed, failed, total, errors = _parse_pytest_output(output)
        assert passed == 3
        assert failed == 2
        assert total == 5

    def test_all_failed(self):
        output = "5 failed in 0.08s\n"
        passed, failed, total, errors = _parse_pytest_output(output)
        assert passed == 0
        assert failed == 5
        assert total == 5

    def test_collects_failed_lines(self):
        output = "FAILED test_foo.py::test_bar - AssertionError\nFAILED test_foo.py::test_baz\n1 passed, 2 failed in 0.05s\n"
        _, _, _, errors = _parse_pytest_output(output)
        assert len(errors) == 2
        assert any("test_bar" in e for e in errors)

    def test_empty_output(self):
        passed, failed, total, errors = _parse_pytest_output("")
        assert passed == 0
        assert failed == 0
        assert total == 0


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------


class TestRunTests:
    """Verify run_tests executes pytest correctly and returns parsed results."""

    def test_correct_impl_all_pass(self, correct_impl_file, tests_file):
        passed, failed, total, errors = run_tests(correct_impl_file, tests_file)
        assert passed == 4
        assert failed == 0
        assert total == 4

    def test_buggy_impl_has_failures(self, buggy_impl_file, tests_file):
        passed, failed, total, errors = run_tests(buggy_impl_file, tests_file)
        assert failed > 0
        assert total == 4

    def test_returns_four_tuple(self, correct_impl_file, tests_file):
        result = run_tests(correct_impl_file, tests_file)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_total_equals_passed_plus_failed(self, buggy_impl_file, tests_file):
        passed, failed, total, _ = run_tests(buggy_impl_file, tests_file)
        assert total == passed + failed

    def test_timeout_returns_zero_counts_and_error(self, slow_impl_file, tests_file):
        passed, failed, total, errors = run_tests(slow_impl_file, tests_file, timeout=2)
        assert passed == 0
        assert failed == 0
        assert total == 0
        assert len(errors) >= 1
        assert any("timeout" in e.lower() or "Timeout" in e for e in errors)

    def test_syntax_error_impl(self, syntax_error_impl_file, tests_file):
        passed, failed, total, errors = run_tests(syntax_error_impl_file, tests_file)
        # A syntax error should result in collection errors, not passing tests
        assert passed == 0
        assert total >= 0  # May show as errors in pytest

    def test_errors_list_type(self, buggy_impl_file, tests_file):
        _, _, _, errors = run_tests(buggy_impl_file, tests_file)
        assert isinstance(errors, list)
        assert all(isinstance(e, str) for e in errors)


# ---------------------------------------------------------------------------
# run_self_eval
# ---------------------------------------------------------------------------


class TestRunSelfEval:
    """Verify run_self_eval runs both blind and tested impls against agent's tests."""

    def test_returns_eval_result(self, card_dir):
        result = run_self_eval(card_dir, "agent_a")
        assert isinstance(result, EvalResult)

    def test_eval_type_is_self(self, card_dir):
        result = run_self_eval(card_dir, "agent_a")
        assert result.eval_type == "self"

    def test_agent_name_set(self, card_dir):
        result = run_self_eval(card_dir, "agent_a")
        assert result.agent == "agent_a"

    def test_card_id_from_dir(self, card_dir):
        result = run_self_eval(card_dir, "agent_a")
        assert result.card_id == card_dir.name

    def test_correct_agent_blind_passes(self, card_dir):
        result = run_self_eval(card_dir, "agent_a")
        assert result.blind_passed == 4
        assert result.blind_failed == 0
        assert result.blind_total == 4

    def test_correct_agent_tested_passes(self, card_dir):
        result = run_self_eval(card_dir, "agent_a")
        assert result.tested_passed == 4
        assert result.tested_failed == 0

    def test_buggy_agent_has_failures(self, card_dir):
        result = run_self_eval(card_dir, "agent_b")
        assert result.blind_failed > 0
        assert result.tested_failed > 0

    def test_missing_agent_dir_reports_errors(self, card_dir):
        result = run_self_eval(card_dir, "nonexistent_agent")
        assert len(result.errors) > 0
        assert result.blind_passed == 0
        assert result.tested_passed == 0


# ---------------------------------------------------------------------------
# run_cross_eval
# ---------------------------------------------------------------------------


class TestRunCrossEval:
    """Verify run_cross_eval produces N*(N-1) results."""

    def test_two_agents_gives_two_results(self, card_dir):
        results = run_cross_eval(card_dir, ["agent_a", "agent_b"])
        assert len(results) == 2  # 2 * (2-1) = 2

    def test_three_agents_gives_six_results(self, card_dir):
        # Create a third agent
        agent_c = card_dir / "agent_c"
        agent_c.mkdir()
        (agent_c / "blind_impl.py").write_text(CORRECT_IMPL)
        (agent_c / "tested_impl.py").write_text(CORRECT_IMPL)
        (agent_c / "tests.py").write_text(TESTS_CODE)

        results = run_cross_eval(card_dir, ["agent_a", "agent_b", "agent_c"])
        assert len(results) == 6  # 3 * (3-1) = 6

    def test_eval_type_contains_cross(self, card_dir):
        results = run_cross_eval(card_dir, ["agent_a", "agent_b"])
        for r in results:
            assert r.eval_type.startswith("cross:")

    def test_no_self_pairs(self, card_dir):
        results = run_cross_eval(card_dir, ["agent_a", "agent_b"])
        for r in results:
            # eval_type is "cross:{test_agent}", agent is impl_agent
            test_agent = r.eval_type.split(":")[1]
            assert r.agent != test_agent

    def test_all_results_are_eval_result(self, card_dir):
        results = run_cross_eval(card_dir, ["agent_a", "agent_b"])
        assert all(isinstance(r, EvalResult) for r in results)

    def test_single_agent_gives_no_results(self, card_dir):
        results = run_cross_eval(card_dir, ["agent_a"])
        assert len(results) == 0


# ---------------------------------------------------------------------------
# run_audited_eval
# ---------------------------------------------------------------------------


class TestRunAuditedEval:
    """Verify run_audited_eval runs all agents against gold-standard tests."""

    def test_returns_one_result_per_agent(self, card_dir, tests_file):
        results = run_audited_eval(card_dir, ["agent_a", "agent_b"], tests_file)
        assert len(results) == 2

    def test_eval_type_is_audited(self, card_dir, tests_file):
        results = run_audited_eval(card_dir, ["agent_a", "agent_b"], tests_file)
        for r in results:
            assert r.eval_type == "audited"

    def test_correct_agent_passes_audited(self, card_dir, tests_file):
        results = run_audited_eval(card_dir, ["agent_a"], tests_file)
        assert results[0].blind_passed == 4
        assert results[0].tested_passed == 4

    def test_buggy_agent_fails_audited(self, card_dir, tests_file):
        results = run_audited_eval(card_dir, ["agent_b"], tests_file)
        assert results[0].blind_failed > 0


# ---------------------------------------------------------------------------
# Integration: correct impl passes more tests than buggy impl (TODO requirement)
# ---------------------------------------------------------------------------


class TestCorrectVsBuggyComparison:
    """As specified in TODO: create correct + buggy impls, verify correct passes more."""

    def test_correct_impl_passes_more_than_buggy(self, correct_impl_file, buggy_impl_file, tests_file):
        cp, cf, ct, _ = run_tests(correct_impl_file, tests_file)
        bp, bf, bt, _ = run_tests(buggy_impl_file, tests_file)
        assert cp > bp, f"Correct impl ({cp} passed) should pass more than buggy ({bp} passed)"

    def test_cross_eval_correct_outperforms_buggy(self, card_dir):
        results = run_cross_eval(card_dir, ["agent_a", "agent_b"])
        a_results = [r for r in results if r.agent == "agent_a"]
        b_results = [r for r in results if r.agent == "agent_b"]
        a_passed = sum(r.blind_passed + r.tested_passed for r in a_results)
        b_passed = sum(r.blind_passed + r.tested_passed for r in b_results)
        assert a_passed > b_passed
