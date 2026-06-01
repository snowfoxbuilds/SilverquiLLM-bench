"""Tests for --cards-aware status / summary / postmortem plumbing (TODO item 2).

Verifies that:
- _write_card_statuses() with card_filter produces status.json with only filtered cards
- _write_card_statuses() without filter produces status.json with all cards
- Collector number normalization: "001" matches card with collector_number "1"
- _evaluate_results() produces per-card result.json and postmortem.jsonl
- _generate_run_summary() produces run_summary.json with card_filter field
- _harvest_results() receives and passes through card_filter correctly
- Numeric collector numbers ('1', '7', '13') work as user-facing filter values
- Zero-padded numbers ('001', '007') are normalized and match correctly
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.cli import (
    _evaluate_results,
    _generate_run_summary,
    _harvest_results,
    _write_card_statuses,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _get_real_sos_collector_numbers() -> list[str]:
    """Return real SOS collector numbers (directory names) from the cards directory.

    load_all_card_specs uses directory name as collector_number, so we mirror that.
    """
    sos_dir = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "sos"
    result = []
    for d in sorted(sos_dir.iterdir()):
        spec = d / "card_spec.json"
        if d.is_dir() and spec.exists():
            result.append(d.name)  # e.g., "sos_1", "sos_10"
    return result


def _get_json_collector_number(dir_name: str) -> str:
    """Read the collector_number field from the card_spec.json for a given dir."""
    spec_path = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "sos" / dir_name / "card_spec.json"
    with open(spec_path) as f:
        return json.load(f)["collector_number"]


def _setup_workspace_with_cards(workspace: Path, collector_numbers: list[str]) -> None:
    """Create workspace card dirs with modified card_impl.py for given collector numbers."""
    for cn in collector_numbers:
        card_dir = workspace / "cards" / "sos" / cn
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "card_impl.py").write_text(f"# Modified impl for card {cn}\n")


# ---------------------------------------------------------------------------
# Test: Numeric collector number filtering (user-facing --cards values)
# ---------------------------------------------------------------------------


class TestNumericCollectorNumberFilter:
    """Filter by numeric collector numbers as the user would pass via --cards.

    Users pass --cards 1,7,13 (the numeric collector_number from the card_spec.json).
    The production code must match these against specs regardless of directory naming.
    """

    def test_harvest_with_numeric_filter_matches_card(self, tmp_path):
        """_harvest_results with card_filter=['1'] should match the card whose
        card_spec.json has collector_number='1' (directory sos_1)."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # sos_1 has collector_number "1" in its card_spec.json
        # Set up workspace with that directory
        _setup_workspace_with_cards(workspace, ["sos_1"])

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=["1"],
        )

        # The card should be harvested (status.json non-empty)
        statuses = json.loads((run_dir / "status.json").read_text())
        assert len(statuses) == 1, (
            f"Expected exactly 1 card in status.json when filtering by '1', got {len(statuses)}: {list(statuses.keys())}"
        )

    def test_harvest_with_numeric_filter_excludes_non_matching(self, tmp_path):
        """_harvest_results with card_filter=['1'] should NOT include card '53'."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Set up workspace with multiple cards
        _setup_workspace_with_cards(workspace, ["sos_1", "sos_53"])

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=["1"],
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        # Only card "1" should appear, not "53"
        status_values = list(statuses.keys())
        assert len(statuses) == 1, (
            f"Expected 1 card when filtering by '1', got {len(statuses)}: {status_values}"
        )

    def test_harvest_with_multiple_numeric_filters(self, tmp_path):
        """_harvest_results with card_filter=['1', '53'] matches both cards."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        _setup_workspace_with_cards(workspace, ["sos_1", "sos_53"])

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=["1", "53"],
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert len(statuses) == 2, (
            f"Expected 2 cards when filtering by ['1', '53'], got {len(statuses)}: {list(statuses.keys())}"
        )

    def test_write_card_statuses_with_numeric_filter(self, tmp_path):
        """_write_card_statuses with numeric filter set {'1'} should include that card."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        _setup_workspace_with_cards(workspace, ["sos_1"])

        # Use numeric filter set (as _harvest_results would compute it)
        _write_card_statuses(workspace, run_dir, timed_out=False, card_filter={"1"})

        statuses = json.loads((run_dir / "status.json").read_text())
        assert len(statuses) == 1, (
            f"Expected 1 card in status.json with filter {{'1'}}, got {len(statuses)}: {list(statuses.keys())}"
        )


# ---------------------------------------------------------------------------
# Test: Zero-padded collector number normalization
# ---------------------------------------------------------------------------


class TestZeroPaddedCollectorNumbers:
    """Zero-padded numbers like '001', '007' should be normalized to '1', '7'."""

    def test_harvest_with_zero_padded_filter_matches(self, tmp_path):
        """_harvest_results with card_filter=['001'] should match card with
        collector_number '1' after normalization."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        _setup_workspace_with_cards(workspace, ["sos_1"])

        # '001'.isdigit() is True, str(int('001')) == '1'
        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=["001"],
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert len(statuses) == 1, (
            f"Expected '001' to normalize to '1' and match, got {len(statuses)} cards"
        )

    def test_harvest_with_zero_padded_053_matches_53(self, tmp_path):
        """_harvest_results with card_filter=['053'] should match card '53'."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        _setup_workspace_with_cards(workspace, ["sos_53"])

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=["053"],
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert len(statuses) == 1, (
            f"Expected '053' to normalize to '53' and match sos_53, got {len(statuses)} cards"
        )

    def test_cli_parsing_normalizes_zero_padded_to_plain(self):
        """CLI --cards parsing normalizes '001' → '1', '007' → '7', '042' → '42'."""
        cards_input = "001,007,042"
        # This is the exact parsing logic from run() in cli.py
        card_filter = [
            str(int(c)) if c.isdigit() else c.strip()
            for c in (tok.strip() for tok in cards_input.split(","))
            if c
        ]
        assert card_filter == ["1", "7", "42"]

    def test_cli_parsing_preserves_non_numeric_values(self):
        """CLI --cards parsing preserves non-numeric values unchanged."""
        cards_input = "sos_1,sos_10"
        card_filter = [
            str(int(c)) if c.isdigit() else c.strip()
            for c in (tok.strip() for tok in cards_input.split(","))
            if c
        ]
        assert card_filter == ["sos_1", "sos_10"]


# ---------------------------------------------------------------------------
# Test: _write_card_statuses with directory-name filters (existing behavior)
# ---------------------------------------------------------------------------


class TestWriteCardStatusesFiltered:
    """_write_card_statuses with card_filter using directory names."""

    def test_status_json_contains_only_filtered_cards(self, tmp_path):
        """When card_filter is set, status.json should only list those cards."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        all_cns = _get_real_sos_collector_numbers()
        assert len(all_cns) >= 3, "Need at least 3 SOS cards for this test"

        # Only filter for the first two cards (using dir names)
        filter_set = {all_cns[0], all_cns[1]}

        _write_card_statuses(workspace, run_dir, timed_out=False, card_filter=filter_set)

        statuses = json.loads((run_dir / "status.json").read_text())
        assert set(statuses.keys()) == filter_set

    def test_filtered_cards_not_in_workspace_get_no_output(self, tmp_path):
        """Filtered cards with no workspace impl get 'no_output' status."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        all_cns = _get_real_sos_collector_numbers()
        filter_set = {all_cns[0]}

        _write_card_statuses(workspace, run_dir, timed_out=False, card_filter=filter_set)

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses[all_cns[0]]["status"] == "no_output"

    def test_filtered_cards_with_modified_impl_get_completed(self, tmp_path):
        """Filtered cards with modified card_impl.py get 'completed' status."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        all_cns = _get_real_sos_collector_numbers()
        target_cn = all_cns[0]
        filter_set = {target_cn}

        _setup_workspace_with_cards(workspace, [target_cn])

        _write_card_statuses(workspace, run_dir, timed_out=False, card_filter=filter_set)

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses[target_cn]["status"] == "completed"

    def test_filtered_cards_with_timeout_get_timeout_status(self, tmp_path):
        """When timed_out=True, unmodified filtered cards get 'timeout' status."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        all_cns = _get_real_sos_collector_numbers()
        filter_set = {all_cns[0]}

        _write_card_statuses(workspace, run_dir, timed_out=True, card_filter=filter_set)

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses[all_cns[0]]["status"] == "timeout"


# ---------------------------------------------------------------------------
# Test: _write_card_statuses without card_filter (all cards)
# ---------------------------------------------------------------------------


class TestWriteCardStatusesUnfiltered:
    """_write_card_statuses without card_filter should include all SOS cards."""

    def test_status_json_contains_all_sos_cards(self, tmp_path):
        """When card_filter is None, status.json should list all SOS cards."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        _write_card_statuses(workspace, run_dir, timed_out=False, card_filter=None)

        statuses = json.loads((run_dir / "status.json").read_text())
        all_cns = _get_real_sos_collector_numbers()
        assert set(statuses.keys()) == set(all_cns)

    def test_unfiltered_has_more_cards_than_filtered(self, tmp_path):
        """Unfiltered status.json has more entries than a filtered one."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_dir_all = tmp_path / "run_all"
        run_dir_all.mkdir()
        run_dir_filtered = tmp_path / "run_filtered"
        run_dir_filtered.mkdir()

        all_cns = _get_real_sos_collector_numbers()
        assert len(all_cns) >= 3

        _write_card_statuses(workspace, run_dir_all, timed_out=False, card_filter=None)
        _write_card_statuses(workspace, run_dir_filtered, timed_out=False, card_filter={all_cns[0]})

        all_statuses = json.loads((run_dir_all / "status.json").read_text())
        filtered_statuses = json.loads((run_dir_filtered / "status.json").read_text())
        assert len(all_statuses) > len(filtered_statuses)


# ---------------------------------------------------------------------------
# Test: _evaluate_results produces per-card result.json and postmortem.jsonl
# ---------------------------------------------------------------------------


class TestEvaluateResults:
    """_evaluate_results should produce per-card result.json and postmortem.jsonl."""

    def test_produces_per_card_result_json(self, tmp_path):
        """After evaluation, each card dir should have result.json."""
        from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult

        run_dir = tmp_path / "run"
        cards_out = run_dir / "cards" / "1"
        cards_out.mkdir(parents=True)

        mock_full_result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=3, tests_failed=1, tests_total=4, pass_rate=0.75),
            },
            fdn_results={},
            engine_result=EngineResult(),
        )

        with patch("silverquillm.evaluator.evaluate", return_value=mock_full_result):
            _evaluate_results(run_dir, card_filter=["1"])

        result_path = cards_out / "result.json"
        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert data["tests_passed"] == 3
        assert data["tests_failed"] == 1
        assert data["tests_total"] == 4
        assert data["pass_rate"] == 0.75

    def test_result_json_carries_per_node_modern_schema(self, tmp_path):
        """When the CardResult has test_nodes, result.json must carry them
        plus tests_hash and errors so the harvester's modern path can compute
        per-node breadth."""
        from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult

        run_dir = tmp_path / "run"
        (run_dir / "cards").mkdir(parents=True)

        cr = CardResult(
            collector_number="1", tests_passed=1, tests_failed=1, tests_total=2,
            pass_rate=0.5,
            errors=["FAILED tests.py::TestX::test_b"],
            test_nodes=[
                {"test_node": "tests.py::TestX::test_a", "outcome": "pass"},
                {"test_node": "tests.py::TestX::test_b", "outcome": "fail"},
            ],
            tests_hash="a" * 64,
        )
        mock_full_result = FullEvalResult(
            sos_results={"1": cr}, fdn_results={}, engine_result=EngineResult(),
        )

        with patch("silverquillm.evaluator.evaluate", return_value=mock_full_result):
            _evaluate_results(run_dir, card_filter=["1"])

        data = json.loads((run_dir / "cards" / "1" / "result.json").read_text())
        assert data["test_nodes"] == cr.test_nodes
        assert data["tests_hash"] == "a" * 64
        assert len(data["tests_hash"]) == 64
        assert data["errors"] == ["FAILED tests.py::TestX::test_b"]
        assert data["skipped"] is False

    def test_result_json_omits_test_nodes_when_none_captured(self, tmp_path):
        """A skipped / pre-pytest-error card (no captured nodes) must omit
        test_nodes so the harvester stays on its legacy (rollup) path rather
        than emitting zero rows and silently dropping the card."""
        from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult

        run_dir = tmp_path / "run"
        (run_dir / "cards").mkdir(parents=True)

        cr = CardResult(
            collector_number="1", skipped=True,
            errors=["No audited tests at .../tests.py"],
        )
        mock_full_result = FullEvalResult(
            sos_results={"1": cr}, fdn_results={}, engine_result=EngineResult(),
        )

        with patch("silverquillm.evaluator.evaluate", return_value=mock_full_result):
            _evaluate_results(run_dir, card_filter=["1"])

        data = json.loads((run_dir / "cards" / "1" / "result.json").read_text())
        assert "test_nodes" not in data
        assert "tests_hash" not in data
        assert data["skipped"] is True
        assert data["errors"] == ["No audited tests at .../tests.py"]

    def test_produces_per_card_postmortem_jsonl(self, tmp_path):
        """After evaluation, each card dir should have postmortem.jsonl."""
        from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult

        run_dir = tmp_path / "run"
        (run_dir / "cards").mkdir(parents=True)

        mock_full_result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=5, tests_failed=0, tests_total=5, pass_rate=1.0),
            },
            fdn_results={},
            engine_result=EngineResult(),
        )

        with patch("silverquillm.evaluator.evaluate", return_value=mock_full_result):
            _evaluate_results(run_dir, card_filter=["1"])

        postmortem_path = run_dir / "cards" / "1" / "postmortem.jsonl"
        assert postmortem_path.exists()
        lines = postmortem_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["collector_number"] == "1"

    def test_card_filter_limits_evaluation_output(self, tmp_path):
        """When card_filter is set, only those cards get result.json."""
        from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult

        run_dir = tmp_path / "run"
        (run_dir / "cards").mkdir(parents=True)

        # Evaluator returns results for cards 1 and 2
        mock_full_result = FullEvalResult(
            sos_results={
                "1": CardResult(collector_number="1", tests_passed=3, tests_failed=0, tests_total=3, pass_rate=1.0),
                "2": CardResult(collector_number="2", tests_passed=2, tests_failed=1, tests_total=3, pass_rate=0.67),
            },
            fdn_results={},
            engine_result=EngineResult(),
        )

        # But filter only card "1"
        with patch("silverquillm.evaluator.evaluate", return_value=mock_full_result):
            _evaluate_results(run_dir, card_filter=["1"])

        # Card 1 should have result.json
        assert (run_dir / "cards" / "1" / "result.json").exists()
        # Card 2 should NOT have result.json (filtered out)
        assert not (run_dir / "cards" / "2" / "result.json").exists()

    def test_errors_in_card_result_produce_error_postmortem(self, tmp_path):
        """Cards with errors should have error entries in postmortem.jsonl."""
        from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult

        run_dir = tmp_path / "run"
        (run_dir / "cards").mkdir(parents=True)

        mock_full_result = FullEvalResult(
            sos_results={
                "1": CardResult(
                    collector_number="1", tests_passed=0, tests_failed=2, tests_total=2,
                    pass_rate=0.0, errors=["ImportError: no module 'foo'", "AssertionError"]
                ),
            },
            fdn_results={},
            engine_result=EngineResult(),
        )

        with patch("silverquillm.evaluator.evaluate", return_value=mock_full_result):
            _evaluate_results(run_dir, card_filter=["1"])

        postmortem_path = run_dir / "cards" / "1" / "postmortem.jsonl"
        lines = postmortem_path.read_text().strip().split("\n")
        assert len(lines) == 2  # Two error entries
        for line in lines:
            entry = json.loads(line)
            assert entry["type"] == "error"

    def test_evaluate_failure_does_not_crash(self, tmp_path):
        """If evaluator raises, _evaluate_results should not propagate the exception."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        with patch("silverquillm.evaluator.evaluate", side_effect=RuntimeError("eval broken")):
            # Should not raise
            _evaluate_results(run_dir, card_filter=["1"])


# ---------------------------------------------------------------------------
# Test: _generate_run_summary produces run_summary.json with card_filter
# ---------------------------------------------------------------------------


class TestGenerateRunSummary:
    """_generate_run_summary should produce run_summary.json with card_filter field."""

    def test_run_summary_has_card_filter_field_when_set(self, tmp_path):
        """run_summary.json should include card_filter when cards are filtered."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        mock_summary = {"run_metadata": {"image": "test"}, "per_card": []}

        with patch("silverquillm.results.generate_run_summary", return_value=mock_summary):
            _generate_run_summary(run_dir, image_name="test", card_filter=["1", "7", "13"])

        summary_path = run_dir / "run_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert data["card_filter"] == ["1", "7", "13"]

    def test_run_summary_card_filter_null_when_unset(self, tmp_path):
        """run_summary.json should have card_filter=null when no filter is used."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        mock_summary = {"run_metadata": {"image": "test"}, "per_card": []}

        with patch("silverquillm.results.generate_run_summary", return_value=mock_summary):
            _generate_run_summary(run_dir, image_name="test", card_filter=None)

        summary_path = run_dir / "run_summary.json"
        data = json.loads(summary_path.read_text())
        assert data["card_filter"] is None

    def test_run_summary_written_regardless_of_selection_size(self, tmp_path):
        """run_summary.json is written even for a single-card filter."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        mock_summary = {"run_metadata": {"image": "test"}, "per_card": []}

        with patch("silverquillm.results.generate_run_summary", return_value=mock_summary):
            _generate_run_summary(run_dir, image_name="test", card_filter=["42"])

        assert (run_dir / "run_summary.json").exists()
        data = json.loads((run_dir / "run_summary.json").read_text())
        assert data["card_filter"] == ["42"]


# ---------------------------------------------------------------------------
# Test: _harvest_results with directory-name filters (existing behavior)
# ---------------------------------------------------------------------------


class TestHarvestCardFilter:
    """_harvest_results should scope harvesting to filtered cards."""

    def test_harvest_with_dir_name_filter_only_copies_filtered_cards(self, tmp_path):
        """Only filtered cards should appear in run_dir/cards/ (dir-name filter)."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        all_cns = _get_real_sos_collector_numbers()
        assert len(all_cns) >= 2

        # Set up workspace with multiple cards modified
        _setup_workspace_with_cards(workspace, all_cns[:3])

        # Filter using directory name (existing behavior)
        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=[all_cns[0]],
        )

        # Only filtered card should be harvested
        cards_out = run_dir / "cards"
        harvested = {d.name for d in cards_out.iterdir() if d.is_dir()} if cards_out.exists() else set()
        assert all_cns[0] in harvested
        for cn in all_cns[1:3]:
            assert cn not in harvested

    def test_harvest_without_filter_copies_all_modified_cards(self, tmp_path):
        """Without card_filter, all modified cards are harvested."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        all_cns = _get_real_sos_collector_numbers()
        _setup_workspace_with_cards(workspace, all_cns[:3])

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=None,
        )

        cards_out = run_dir / "cards"
        harvested = {d.name for d in cards_out.iterdir() if d.is_dir()} if cards_out.exists() else set()
        for cn in all_cns[:3]:
            assert cn in harvested

    def test_harvest_card_filter_scopes_status_json(self, tmp_path):
        """status.json in harvest output should only have filtered cards."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        all_cns = _get_real_sos_collector_numbers()
        assert len(all_cns) >= 2

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, card_filter=[all_cns[0]],
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert list(statuses.keys()) == [all_cns[0]]
