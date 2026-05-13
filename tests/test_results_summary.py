"""Tests for TODO item 9: run summary generation.

Tests verify:
- Basic summary generation with required top-level keys.
- Aggregation math (pass rates computed correctly).
- Per-card details include collector_number, status, audited_passed, audited_total.
- Partial results (timeout cards with no result.json).
- Missing status.json handled gracefully.
- Missing eval_result.json handled gracefully.
- Engine churn lines counted from engine_diff.patch.
- No engine_diff.patch → engine_churn_lines = 0.
- run_summary.json written to disk.
- Card names read from card_spec.json.
- harness_version captured via git rev-parse.
- All tests pass → 100% pass rates.
- All tests fail → 0% pass rates.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.results import generate_run_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card_dir(
    run_dir: Path,
    num: str,
    *,
    passed: int = 0,
    failed: int = 0,
    total: int | None = None,
    card_name: str = "",
    skip_result: bool = False,
):
    """Create a card directory with result.json and optionally card_spec.json."""
    card_dir = run_dir / "cards" / num
    card_dir.mkdir(parents=True, exist_ok=True)

    if not skip_result:
        if total is None:
            total = passed + failed
        result = {
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_total": total,
        }
        (card_dir / "result.json").write_text(json.dumps(result))

    if card_name:
        spec = {"name": card_name, "collector_number": num}
        (card_dir / "card_spec.json").write_text(json.dumps(spec))


def _make_status(run_dir: Path, status_map: dict[str, str]):
    """Write status.json."""
    (run_dir / "status.json").write_text(json.dumps(status_map))


def _make_eval_result(run_dir: Path, eval_data: dict):
    """Write eval_result.json."""
    (run_dir / "eval_result.json").write_text(json.dumps(eval_data))


# ---------------------------------------------------------------------------
# Test: Basic summary generation
# ---------------------------------------------------------------------------


class TestBasicSummaryGeneration:
    def test_output_has_all_required_top_level_keys(self, tmp_path):
        """Summary must contain run_metadata, sos_card_correctness, fdn_regression, engine_regression, per_card."""
        _make_status(tmp_path, {"1": "completed", "2": "completed", "3": "no_output"})
        _make_card_dir(tmp_path, "1", passed=3, failed=1, card_name="Alpha Card")
        _make_card_dir(tmp_path, "2", passed=5, failed=0, card_name="Beta Card")
        _make_card_dir(tmp_path, "3", skip_result=True)

        with patch("silverquillm.results._get_harness_version", return_value="abc123"):
            result = generate_run_summary(tmp_path, "opencode-tested")

        assert "run_metadata" in result
        assert "sos_card_correctness" in result
        assert "fdn_regression" in result
        assert "engine_regression" in result
        assert "per_card" in result

    def test_run_metadata_contains_image_name(self, tmp_path):
        _make_status(tmp_path, {"1": "completed"})
        _make_card_dir(tmp_path, "1", passed=2, failed=0)

        with patch("silverquillm.results._get_harness_version", return_value="abc123"):
            result = generate_run_summary(tmp_path, "opencode-blind")

        assert result["run_metadata"]["image"] == "opencode-blind"

    def test_run_metadata_has_card_count(self, tmp_path):
        _make_status(tmp_path, {"1": "completed", "2": "completed"})
        _make_card_dir(tmp_path, "1", passed=1, failed=0)
        _make_card_dir(tmp_path, "2", passed=1, failed=0)

        with patch("silverquillm.results._get_harness_version", return_value="abc123"):
            result = generate_run_summary(tmp_path, "test-image")

        assert result["run_metadata"]["card_count"] == 2


# ---------------------------------------------------------------------------
# Test: Aggregation math
# ---------------------------------------------------------------------------


class TestAggregationMath:
    def test_audited_pass_rate_from_eval_result(self, tmp_path):
        """audited_pass_rate should be total_passed/total_tests from SOS results."""
        _make_status(tmp_path, {"1": "completed", "2": "completed"})
        _make_card_dir(tmp_path, "1", passed=3, failed=1)
        _make_card_dir(tmp_path, "2", passed=5, failed=0)
        _make_eval_result(tmp_path, {
            "sos_results": {
                "1": {"tests_passed": 3, "tests_failed": 1, "tests_total": 4},
                "2": {"tests_passed": 5, "tests_failed": 0, "tests_total": 5},
            },
            "fdn_results": {},
            "engine_result": {},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # 8 passed / 9 total = 0.8889
        assert result["sos_card_correctness"]["audited_pass_rate"] == round(8 / 9, 4)

    def test_card_pass_rate_counts_fully_passing_cards(self, tmp_path):
        """card_pass_rate = cards_with_all_tests_passing / cards_completed."""
        _make_status(tmp_path, {"1": "completed", "2": "completed", "3": "completed"})
        _make_card_dir(tmp_path, "1", passed=4, failed=0)
        _make_card_dir(tmp_path, "2", passed=3, failed=2)
        _make_card_dir(tmp_path, "3", passed=5, failed=0)
        _make_eval_result(tmp_path, {
            "sos_results": {
                "1": {"tests_passed": 4, "tests_failed": 0, "tests_total": 4},
                "2": {"tests_passed": 3, "tests_failed": 2, "tests_total": 5},
                "3": {"tests_passed": 5, "tests_failed": 0, "tests_total": 5},
            },
            "fdn_results": {},
            "engine_result": {},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # 2 out of 3 cards fully pass
        assert result["sos_card_correctness"]["card_pass_rate"] == round(2 / 3, 4)

    def test_fdn_test_pass_rate(self, tmp_path):
        """fdn_test_pass_rate from eval_result's fdn_results."""
        _make_status(tmp_path, {})
        (tmp_path / "cards").mkdir()
        _make_eval_result(tmp_path, {
            "sos_results": {},
            "fdn_results": {
                "100": {"tests_passed": 8, "tests_failed": 2, "tests_total": 10},
                "101": {"tests_passed": 10, "tests_failed": 0, "tests_total": 10},
            },
            "engine_result": {},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # 18/20 = 0.9
        assert result["fdn_regression"]["fdn_test_pass_rate"] == 0.9

    def test_fdn_card_pass_rate(self, tmp_path):
        """fdn_card_pass_rate = fully-passing FDN cards / total FDN cards."""
        _make_status(tmp_path, {})
        (tmp_path / "cards").mkdir()
        _make_eval_result(tmp_path, {
            "sos_results": {},
            "fdn_results": {
                "100": {"tests_passed": 10, "tests_failed": 0, "tests_total": 10},
                "101": {"tests_passed": 9, "tests_failed": 1, "tests_total": 10},
                "102": {"tests_passed": 5, "tests_failed": 0, "tests_total": 5},
            },
            "engine_result": {},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # 2 out of 3 FDN cards fully pass
        assert result["fdn_regression"]["fdn_card_pass_rate"] == round(2 / 3, 4)

    def test_engine_test_pass_rate(self, tmp_path):
        """engine_test_pass_rate from eval_result's engine_result."""
        _make_status(tmp_path, {})
        (tmp_path / "cards").mkdir()
        _make_eval_result(tmp_path, {
            "sos_results": {},
            "fdn_results": {},
            "engine_result": {"tests_passed": 7, "tests_failed": 3, "tests_total": 10},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["engine_regression"]["engine_test_pass_rate"] == 0.7


# ---------------------------------------------------------------------------
# Test: Per-card details
# ---------------------------------------------------------------------------


class TestPerCardDetails:
    def test_per_card_has_correct_entries(self, tmp_path):
        _make_status(tmp_path, {"1": "completed", "2": "completed"})
        _make_card_dir(tmp_path, "1", passed=3, failed=1, card_name="Card One")
        _make_card_dir(tmp_path, "2", passed=5, failed=0, card_name="Card Two")

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        per_card = result["per_card"]
        assert len(per_card) == 2

        card1 = per_card[0]
        assert card1["collector_number"] == "1"
        assert card1["status"] == "completed"
        assert card1["audited_passed"] == 3
        assert card1["audited_total"] == 4

        card2 = per_card[1]
        assert card2["collector_number"] == "2"
        assert card2["audited_passed"] == 5
        assert card2["audited_total"] == 5


# ---------------------------------------------------------------------------
# Test: Partial results (timeout)
# ---------------------------------------------------------------------------


class TestPartialResults:
    def test_timeout_card_with_no_result_json(self, tmp_path):
        """Timed-out cards with no result.json should appear with 0 test counts."""
        _make_status(tmp_path, {"1": "completed", "2": "timeout"})
        _make_card_dir(tmp_path, "1", passed=4, failed=0)
        _make_card_dir(tmp_path, "2", skip_result=True)

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        per_card = result["per_card"]
        timeout_card = [c for c in per_card if c["collector_number"] == "2"][0]
        assert timeout_card["status"] == "timeout"
        assert timeout_card["audited_passed"] == 0
        assert timeout_card["audited_total"] == 0

    def test_timeout_counted_in_sos_card_correctness(self, tmp_path):
        _make_status(tmp_path, {"1": "completed", "2": "timeout"})
        _make_card_dir(tmp_path, "1", passed=4, failed=0)
        _make_card_dir(tmp_path, "2", skip_result=True)

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["sos_card_correctness"]["cards_timed_out"] == 1
        assert result["sos_card_correctness"]["cards_completed"] == 1


# ---------------------------------------------------------------------------
# Test: Missing status.json
# ---------------------------------------------------------------------------


class TestMissingStatusJson:
    def test_no_status_json_defaults_gracefully(self, tmp_path):
        """If status.json is missing, cards should still be processed."""
        _make_card_dir(tmp_path, "1", passed=2, failed=1)

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # Should not crash; per_card still populated
        assert len(result["per_card"]) == 1
        # Default status should be "completed" when not in status_map
        assert result["per_card"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# Test: Missing eval_result.json
# ---------------------------------------------------------------------------


class TestMissingEvalResult:
    def test_no_eval_result_uses_per_card_fallback(self, tmp_path):
        """Without eval_result.json, aggregation falls back to per-card result.json."""
        _make_status(tmp_path, {"1": "completed", "2": "completed"})
        _make_card_dir(tmp_path, "1", passed=3, failed=1)
        _make_card_dir(tmp_path, "2", passed=5, failed=0)

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # Should still compute SOS pass rate from per-card data
        assert result["sos_card_correctness"]["audited_pass_rate"] == round(8 / 9, 4)


# ---------------------------------------------------------------------------
# Test: Engine churn lines
# ---------------------------------------------------------------------------


class TestEngineChurnLines:
    def test_counts_added_and_removed_lines(self, tmp_path):
        """engine_churn_lines counts + and - lines excluding +++ and --- headers."""
        patch_content = """\
--- a/engine/game.py
+++ b/engine/game.py
@@ -10,3 +10,4 @@
 unchanged line
-removed line
+added line one
+added line two
"""
        (tmp_path / "engine_diff.patch").write_text(patch_content)
        _make_status(tmp_path, {})
        (tmp_path / "cards").mkdir()

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        # 3 lines: -removed, +added one, +added two (not --- or +++)
        assert result["engine_regression"]["engine_churn_lines"] == 3

    def test_no_engine_diff_patch_yields_zero(self, tmp_path):
        """No engine_diff.patch → engine_churn_lines = 0."""
        _make_status(tmp_path, {})
        (tmp_path / "cards").mkdir()

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["engine_regression"]["engine_churn_lines"] == 0


# ---------------------------------------------------------------------------
# Test: run_summary.json written to disk
# ---------------------------------------------------------------------------


class TestSummaryWrittenToDisk:
    def test_run_summary_json_created(self, tmp_path):
        """generate_run_summary should write run_summary.json in run_dir."""
        _make_status(tmp_path, {"1": "completed"})
        _make_card_dir(tmp_path, "1", passed=2, failed=0)

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            generate_run_summary(tmp_path, "test")

        summary_path = tmp_path / "run_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert "run_metadata" in data
        assert data["run_metadata"]["image"] == "test"


# ---------------------------------------------------------------------------
# Test: Card name from card_spec.json
# ---------------------------------------------------------------------------


class TestCardNameFromSpec:
    def test_card_name_read_from_spec(self, tmp_path):
        _make_status(tmp_path, {"42": "completed"})
        _make_card_dir(tmp_path, "42", passed=1, failed=0, card_name="Lightning Bolt")

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["per_card"][0]["card_name"] == "Lightning Bolt"

    def test_missing_card_spec_yields_empty_name(self, tmp_path):
        _make_status(tmp_path, {"42": "completed"})
        _make_card_dir(tmp_path, "42", passed=1, failed=0)  # no card_name → no spec

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["per_card"][0]["card_name"] == ""


# ---------------------------------------------------------------------------
# Test: harness_version
# ---------------------------------------------------------------------------


class TestHarnessVersion:
    def test_harness_version_captured(self, tmp_path):
        _make_status(tmp_path, {})
        (tmp_path / "cards").mkdir()

        with patch("silverquillm.results._get_harness_version", return_value="deadbeef1234"):
            result = generate_run_summary(tmp_path, "test")

        assert result["run_metadata"]["harness_version"] == "deadbeef1234"


# ---------------------------------------------------------------------------
# Test: All pass / All fail scenarios
# ---------------------------------------------------------------------------


class TestAllPassScenario:
    def test_100_percent_pass_rates(self, tmp_path):
        _make_status(tmp_path, {"1": "completed", "2": "completed"})
        _make_card_dir(tmp_path, "1", passed=5, failed=0)
        _make_card_dir(tmp_path, "2", passed=3, failed=0)
        _make_eval_result(tmp_path, {
            "sos_results": {
                "1": {"tests_passed": 5, "tests_failed": 0, "tests_total": 5},
                "2": {"tests_passed": 3, "tests_failed": 0, "tests_total": 3},
            },
            "fdn_results": {
                "100": {"tests_passed": 10, "tests_failed": 0, "tests_total": 10},
            },
            "engine_result": {"tests_passed": 20, "tests_failed": 0, "tests_total": 20},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["sos_card_correctness"]["audited_pass_rate"] == 1.0
        assert result["sos_card_correctness"]["card_pass_rate"] == 1.0
        assert result["fdn_regression"]["fdn_test_pass_rate"] == 1.0
        assert result["fdn_regression"]["fdn_card_pass_rate"] == 1.0
        assert result["engine_regression"]["engine_test_pass_rate"] == 1.0


class TestAllFailScenario:
    def test_zero_percent_pass_rates(self, tmp_path):
        _make_status(tmp_path, {"1": "completed", "2": "completed"})
        _make_card_dir(tmp_path, "1", passed=0, failed=5)
        _make_card_dir(tmp_path, "2", passed=0, failed=3)
        _make_eval_result(tmp_path, {
            "sos_results": {
                "1": {"tests_passed": 0, "tests_failed": 5, "tests_total": 5},
                "2": {"tests_passed": 0, "tests_failed": 3, "tests_total": 3},
            },
            "fdn_results": {
                "100": {"tests_passed": 0, "tests_failed": 10, "tests_total": 10},
            },
            "engine_result": {"tests_passed": 0, "tests_failed": 20, "tests_total": 20},
        })

        with patch("silverquillm.results._get_harness_version", return_value="abc"):
            result = generate_run_summary(tmp_path, "test")

        assert result["sos_card_correctness"]["audited_pass_rate"] == 0.0
        assert result["sos_card_correctness"]["card_pass_rate"] == 0.0
        assert result["fdn_regression"]["fdn_test_pass_rate"] == 0.0
        assert result["fdn_regression"]["fdn_card_pass_rate"] == 0.0
        assert result["engine_regression"]["engine_test_pass_rate"] == 0.0
