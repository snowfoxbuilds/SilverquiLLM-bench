"""Additional tests for tests_hash feature — gaps not covered by test_tests_hash.py.

Covers:
- Missing card_impl.py branch: tests_hash is "" and no result.json is written.
- FDN path does not stamp tests_hash (feature is scoped to SOS only).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.evaluator import (
    CardResult,
    FullEvalResult,
    evaluate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pytest_result(passed: int, failed: int) -> MagicMock:
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


# ---------------------------------------------------------------------------
# Missing card_impl.py: tests_hash should be "" and no result.json written
# ---------------------------------------------------------------------------


class TestTestsHashMissingCardImpl:
    """When the agent's card_impl.py is absent, tests_hash stays ""
    and no result.json is written for that card.
    """

    @patch("silverquillm.evaluator.subprocess.run")
    def test_missing_card_impl_tests_hash_is_empty(self, mock_run, tmp_path):
        """When card_impl.py is missing, tests_hash on the CardResult is ""."""
        # Build run_dir with status "completed" but NO card_impl.py
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text(json.dumps({"99": "completed"}))
        # Deliberately do NOT create run_dir/cards/99/card_impl.py

        # Create audited test file
        sos_dir = (
            tmp_path
            / "benchmarks"
            / "sos"
            / "data"
            / "tests"
            / "audited"
            / "sos"
            / "99"
        )
        sos_dir.mkdir(parents=True)
        (sos_dir / "tests.py").write_text("def test_x():\n    assert True\n")

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir()
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        assert "99" in result.sos_results
        cr = result.sos_results["99"]
        assert cr.tests_hash == ""

    @patch("silverquillm.evaluator.subprocess.run")
    def test_missing_card_impl_no_result_json(self, mock_run, tmp_path):
        """When card_impl.py is missing, result.json should NOT be written."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text(json.dumps({"99": "completed"}))

        sos_dir = (
            tmp_path
            / "benchmarks"
            / "sos"
            / "data"
            / "tests"
            / "audited"
            / "sos"
            / "99"
        )
        sos_dir.mkdir(parents=True)
        (sos_dir / "tests.py").write_text("def test_x():\n    assert True\n")

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir()
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        # No result.json should exist since card_impl.py was missing
        result_json = run_dir / "cards" / "99" / "result.json"
        assert not result_json.exists()

    @patch("silverquillm.evaluator.subprocess.run")
    def test_missing_card_impl_has_error_message(self, mock_run, tmp_path):
        """When card_impl.py is missing, the CardResult should record an error."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text(json.dumps({"99": "completed"}))

        sos_dir = (
            tmp_path
            / "benchmarks"
            / "sos"
            / "data"
            / "tests"
            / "audited"
            / "sos"
            / "99"
        )
        sos_dir.mkdir(parents=True)
        (sos_dir / "tests.py").write_text("def test_x():\n    assert True\n")

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir()
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=0, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=10)

        cr = result.sos_results["99"]
        assert len(cr.errors) > 0
        assert any("card_impl" in e for e in cr.errors)


# ---------------------------------------------------------------------------
# FDN path: tests_hash is NOT stamped (feature scoped to SOS only)
# ---------------------------------------------------------------------------


class TestTestsHashNotStampedForFDN:
    """FDN card results should have tests_hash=="" because _eval_fdn_cards
    does not stamp the field — the tests_hash feature is SOS-only.
    """

    @patch("silverquillm.evaluator.subprocess.run")
    def test_fdn_card_result_tests_hash_is_empty(self, mock_run, tmp_path):
        """CardResult objects in fdn_results should always have tests_hash=""."""
        # No SOS completed cards — only FDN
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "status.json").write_text(json.dumps({}))

        # Create an FDN audited test and reference impl
        fdn_audited = (
            tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "F1"
        )
        fdn_audited.mkdir(parents=True)
        (fdn_audited / "tests.py").write_text("def test_fdn():\n    assert True\n")

        # Reference impl for FDN card
        fdn_ref = tmp_path / "cards" / "fdn" / "F1"
        fdn_ref.mkdir(parents=True)
        (fdn_ref / "card_impl.py").write_text("# fdn reference impl\n")

        engine_dir = tmp_path / "engine"
        engine_dir.mkdir()

        mock_run.return_value = _make_pytest_result(passed=1, failed=0)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, tmp_path / "cards", engine_dir, timeout=10)

        assert "F1" in result.fdn_results
        fdn_cr = result.fdn_results["F1"]
        # FDN results must NOT have tests_hash stamped
        assert fdn_cr.tests_hash == ""
