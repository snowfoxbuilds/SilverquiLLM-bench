"""Tests for TODO item 1: Stamp tests_hash into per-card SOS result.json.

Tests verify:
- result.json for an evaluated SOS card contains tests_hash equal to
  sha256(audited tests.py bytes).hexdigest().
- The hash is deterministic (same input -> same hash across two evals).
- Editing the audited tests.py bytes changes the hash.
- When the audited test file is absent/unreadable, tests_hash is "" and
  eval does not crash; existing counts/errors behavior is unchanged.
- CardResult dataclass includes tests_hash field with default "".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, fields as dc_fields
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.evaluator import (
    CardResult,
    FullEvalResult,
    evaluate,
)


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_evaluator_3dim.py)
# ---------------------------------------------------------------------------


def _make_pytest_result(passed: int, failed: int) -> MagicMock:
    """Create a mock subprocess.CompletedProcess with pytest-like output."""
    parts = []
    if passed:
        parts.append(f"{passed} passed")
    if failed:
        parts.append(f"{failed} failed")
    summary = ", ".join(parts) + " in 0.05s"
    mock = MagicMock()
    mock.stdout = summary + "\n"
    mock.stderr = ""
    mock.returncode = 0 if failed == 0 else 1
    return mock


def _setup_run_dir(tmp_path: Path, completed_cards: list[str]) -> Path:
    """Build a minimal run_dir with status.json and card_impl.py stubs."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    status = {cn: "completed" for cn in completed_cards}
    (run_dir / "status.json").write_text(json.dumps(status))
    for cn in completed_cards:
        card_dir = run_dir / "cards" / cn
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "card_impl.py").write_text(f"# impl for {cn}\n")
    return run_dir


def _setup_audited_sos(tmp_path: Path, card_tests: dict[str, str]) -> Path:
    """Create audited SOS test files with specified content.

    Parameters
    ----------
    card_tests:
        Mapping of collector_number -> tests.py content.
    """
    sos_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
    for cn, content in card_tests.items():
        d = sos_dir / cn
        d.mkdir(parents=True, exist_ok=True)
        (d / "tests.py").write_text(content)
    return sos_dir


def _setup_audited_sos_simple(tmp_path: Path, card_numbers: list[str]) -> Path:
    """Create audited SOS test files with default content."""
    return _setup_audited_sos(
        tmp_path,
        {cn: f"# audited tests for SOS {cn}\n" for cn in card_numbers},
    )


def _run_evaluate_with_mocked_pytest(
    tmp_path: Path,
    completed_cards: list[str],
    card_tests: dict[str, str],
    pytest_result: MagicMock | None = None,
) -> FullEvalResult:
    """Set up dirs and call evaluate() with subprocess mocked."""
    run_dir = _setup_run_dir(tmp_path, completed_cards)
    _setup_audited_sos(tmp_path, card_tests)

    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(exist_ok=True)
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir(exist_ok=True)

    if pytest_result is None:
        pytest_result = _make_pytest_result(passed=2, failed=0)

    with (
        patch("silverquillm.evaluator._REPO_ROOT", tmp_path),
        patch("silverquillm.evaluator.subprocess.run", return_value=pytest_result),
    ):
        return evaluate(run_dir, cards_dir, engine_dir, timeout=10)


# ---------------------------------------------------------------------------
# CardResult dataclass: tests_hash field
# ---------------------------------------------------------------------------


class TestCardResultTestsHashField:
    """Verify CardResult has tests_hash with correct default."""

    def test_tests_hash_field_exists(self):
        field_names = {f.name for f in dc_fields(CardResult)}
        assert "tests_hash" in field_names

    def test_tests_hash_default_is_empty_string(self):
        cr = CardResult(collector_number="1")
        assert cr.tests_hash == ""

    def test_tests_hash_serialized_via_asdict(self):
        cr = CardResult(collector_number="1", tests_hash="abc123")
        d = asdict(cr)
        assert d["tests_hash"] == "abc123"

    def test_tests_hash_type_is_str(self):
        field_map = {f.name: f for f in dc_fields(CardResult)}
        assert field_map["tests_hash"].type == "str"


# ---------------------------------------------------------------------------
# tests_hash equals SHA-256 of audited tests.py bytes
# ---------------------------------------------------------------------------


class TestTestsHashCorrectValue:
    """Verify tests_hash in result.json matches sha256(tests.py bytes)."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_result_json_contains_correct_tests_hash(self, mock_run, tmp_path):
        """result.json for an evaluated SOS card should contain tests_hash
        equal to hashlib.sha256(<bytes of the audited tests.py>).hexdigest().
        """
        test_content = "def test_something():\n    assert True\n"
        expected_hash = hashlib.sha256(test_content.encode()).hexdigest()

        run_dir = _setup_run_dir(tmp_path, ["42"])
        _setup_audited_sos(tmp_path, {"42": test_content})
        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        mock_run.return_value = _make_pytest_result(passed=1, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        # Check in-memory CardResult
        assert "42" in result.sos_results
        cr = result.sos_results["42"]
        assert cr.tests_hash == expected_hash

        # Check persisted result.json
        result_json = run_dir / "cards" / "42" / "result.json"
        assert result_json.exists()
        data = json.loads(result_json.read_text())
        assert data["tests_hash"] == expected_hash

    @patch("silverquillm.evaluator.subprocess.run")
    def test_hash_is_64_char_hex(self, mock_run, tmp_path):
        """SHA-256 hex digest should be exactly 64 lowercase hex characters."""
        run_dir = _setup_run_dir(tmp_path, ["7"])
        _setup_audited_sos_simple(tmp_path, ["7"])
        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        mock_run.return_value = _make_pytest_result(passed=1, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        h = result.sos_results["7"].tests_hash
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestTestsHashDeterminism:
    """Verify the hash is deterministic: same input -> same hash."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_same_input_produces_same_hash(self, mock_run, tmp_path):
        """Running eval twice on the same audited tests.py produces
        identical tests_hash values.
        """
        test_content = "import math\ndef test_pi():\n    assert math.pi > 3\n"

        mock_run.return_value = _make_pytest_result(passed=1, failed=0)

        # First evaluation
        run_dir_1 = tmp_path / "run1" / "run"
        run_dir_1.mkdir(parents=True)
        status = {"55": "completed"}
        (run_dir_1 / "status.json").write_text(json.dumps(status))
        card_dir_1 = run_dir_1 / "cards" / "55"
        card_dir_1.mkdir(parents=True)
        (card_dir_1 / "card_impl.py").write_text("# impl\n")

        sos_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "55"
        sos_dir.mkdir(parents=True)
        (sos_dir / "tests.py").write_text(test_content)

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result1 = evaluate(run_dir_1, cards_dir, engine_dir, timeout=10)

        hash1 = result1.sos_results["55"].tests_hash

        # Second evaluation — different run_dir but same audited tests
        run_dir_2 = tmp_path / "run2" / "run"
        run_dir_2.mkdir(parents=True)
        (run_dir_2 / "status.json").write_text(json.dumps(status))
        card_dir_2 = run_dir_2 / "cards" / "55"
        card_dir_2.mkdir(parents=True)
        (card_dir_2 / "card_impl.py").write_text("# different impl\n")

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result2 = evaluate(run_dir_2, cards_dir, engine_dir, timeout=10)

        hash2 = result2.sos_results["55"].tests_hash

        assert hash1 == hash2
        assert hash1 != ""  # Sanity: not empty


# ---------------------------------------------------------------------------
# Editing tests.py changes the hash
# ---------------------------------------------------------------------------


class TestTestsHashChangesOnEdit:
    """Verify that modifying audited tests.py changes the hash."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_different_content_produces_different_hash(self, mock_run, tmp_path):
        """Editing audited tests.py bytes should change the tests_hash."""
        content_v1 = "def test_v1():\n    assert 1 + 1 == 2\n"
        content_v2 = "def test_v2():\n    assert 2 + 2 == 4\n"

        mock_run.return_value = _make_pytest_result(passed=1, failed=0)

        # Eval with v1
        run_dir = _setup_run_dir(tmp_path, ["33"])
        sos_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "33"
        sos_dir.mkdir(parents=True, exist_ok=True)
        test_file = sos_dir / "tests.py"
        test_file.write_text(content_v1)

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result_v1 = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        hash_v1 = result_v1.sos_results["33"].tests_hash

        # Edit the audited test file
        test_file.write_text(content_v2)

        # Re-eval with a fresh run_dir (so result.json write doesn't conflict)
        run_dir_2 = tmp_path / "run2"
        run_dir_2.mkdir()
        (run_dir_2 / "status.json").write_text(json.dumps({"33": "completed"}))
        card_dir_2 = run_dir_2 / "cards" / "33"
        card_dir_2.mkdir(parents=True)
        (card_dir_2 / "card_impl.py").write_text("# impl\n")

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result_v2 = evaluate(run_dir_2, cards_dir, engine_dir, timeout=10)

        hash_v2 = result_v2.sos_results["33"].tests_hash

        assert hash_v1 != hash_v2
        # Verify both are actual SHA-256 hashes, not empty strings
        assert len(hash_v1) == 64
        assert len(hash_v2) == 64

        # Cross-check: hashes match what we'd compute independently
        assert hash_v1 == hashlib.sha256(content_v1.encode()).hexdigest()
        assert hash_v2 == hashlib.sha256(content_v2.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Edge: absent/unreadable audited test file
# ---------------------------------------------------------------------------


class TestTestsHashMissingTestFile:
    """Verify behavior when audited test file is absent or unreadable."""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_absent_test_file_gives_empty_hash_and_skipped(self, mock_run, tmp_path):
        """When audited tests.py is absent, tests_hash should be "" and
        the card should be skipped (existing behavior preserved).
        """
        run_dir = _setup_run_dir(tmp_path, ["77"])
        # Create the audited SOS root but do NOT create tests.py for card 77
        sos_root = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        sos_root.mkdir(parents=True, exist_ok=True)

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        # Card should be present in results with skipped=True and
        # tests_hash should be "" (default)
        assert "77" in result.sos_results
        cr = result.sos_results["77"]
        assert cr.tests_hash == ""
        assert cr.skipped is True
        assert len(cr.errors) > 0  # Should have an error about missing tests

    @patch("silverquillm.evaluator.subprocess.run")
    def test_absent_test_file_does_not_crash(self, mock_run, tmp_path):
        """evaluate() should not raise when audited tests.py is missing."""
        run_dir = _setup_run_dir(tmp_path, ["88"])
        sos_root = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        sos_root.mkdir(parents=True, exist_ok=True)

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        # This should NOT raise
        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert isinstance(result, FullEvalResult)

    @patch("silverquillm.evaluator.subprocess.run")
    def test_absent_test_file_preserves_counts(self, mock_run, tmp_path):
        """When audited tests.py is missing, test counts should be zero
        (existing behavior unchanged).
        """
        run_dir = _setup_run_dir(tmp_path, ["66"])
        sos_root = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        sos_root.mkdir(parents=True, exist_ok=True)

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        cr = result.sos_results["66"]
        assert cr.tests_passed == 0
        assert cr.tests_failed == 0
        assert cr.tests_total == 0


# ---------------------------------------------------------------------------
# Existing CardResult fields are preserved (additive-only check)
# ---------------------------------------------------------------------------


class TestAdditiveChange:
    """Confirm tests_hash addition doesn't disrupt existing fields."""

    def test_existing_fields_still_present(self):
        """All pre-existing CardResult fields should still exist."""
        field_names = {f.name for f in dc_fields(CardResult)}
        expected_existing = {
            "collector_number",
            "tests_passed",
            "tests_failed",
            "tests_total",
            "pass_rate",
            "errors",
            "skipped",
        }
        assert expected_existing <= field_names

    @patch("silverquillm.evaluator.subprocess.run")
    def test_result_json_contains_all_existing_fields_plus_tests_hash(
        self, mock_run, tmp_path
    ):
        """result.json should carry all existing CardResult fields alongside
        the new tests_hash field.
        """
        test_content = "# tests\n"
        run_dir = _setup_run_dir(tmp_path, ["15"])
        _setup_audited_sos(tmp_path, {"15": test_content})
        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        mock_run.return_value = _make_pytest_result(passed=2, failed=1)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        result_json = run_dir / "cards" / "15" / "result.json"
        data = json.loads(result_json.read_text())

        # All existing fields
        assert data["collector_number"] == "15"
        assert data["tests_passed"] == 2
        assert data["tests_failed"] == 1
        assert data["tests_total"] == 3
        assert "pass_rate" in data
        assert "errors" in data
        assert "skipped" in data
        # New field
        assert "tests_hash" in data
        assert data["tests_hash"] == hashlib.sha256(test_content.encode()).hexdigest()
