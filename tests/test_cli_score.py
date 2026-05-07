"""Tests for TODO item 8: Wire `benchmark score` command.

Tests verify:
- `benchmark score --results-dir <dir> --tier-data <path>` exits 0 and prints leaderboard.
- `leaderboard.md` is written to results_dir.
- `summary.json` is written to results_dir.
- With custom `--tier-data` path, tier data is loaded correctly.
- Missing `results.json` produces a graceful (empty) result or error.
- Leaderboard output contains expected formatting (table headers).
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from benchmark.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tier_data(tmp_path: Path, cards: list[str] | None = None) -> Path:
    """Create a tier data JSON file (classified format)."""
    cards = cards or ["card-001", "card-002"]
    entries = [
        {"collector_number": cid, "tier": "simple", "name": f"Card {cid}"}
        for cid in cards
    ]
    tier_file = tmp_path / "classified.json"
    tier_file.write_text(json.dumps(entries))
    return tier_file


def _make_results_dir(tmp_path: Path, card_ids: list[str] | None = None) -> Path:
    """Create a results directory with a results.json containing eval data."""
    card_ids = card_ids or ["card-001", "card-002"]
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Create a run subdir so run_dirs is non-empty
    run_dir = results_dir / "run-001"
    run_dir.mkdir()
    cards_dir = run_dir / "cards"
    cards_dir.mkdir()
    for cid in card_ids:
        (cards_dir / cid).mkdir()

    # Create results.json with minimal eval data
    results = []
    for cid in card_ids:
        results.append({
            "agent": "test-agent",
            "card_id": cid,
            "eval_type": "audited",
            "blind_passed": 3,
            "blind_total": 5,
            "tested_passed": 4,
            "tested_total": 5,
        })
        results.append({
            "agent": "test-agent",
            "card_id": cid,
            "eval_type": "cross",
            "blind_passed": 2,
            "blind_total": 5,
            "tested_passed": 3,
            "tested_total": 5,
        })

    (results_dir / "results.json").write_text(json.dumps(results))
    return results_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScoreCommandBasic:
    """Test the basic `benchmark score` command behavior."""

    def test_exits_zero_with_valid_inputs(self, tmp_path: Path) -> None:
        """benchmark score exits 0 with valid results dir and tier data."""
        results_dir = _make_results_dir(tmp_path)
        tier_file = _make_tier_data(tmp_path, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"

    def test_prints_leaderboard_to_stdout(self, tmp_path: Path) -> None:
        """benchmark score prints leaderboard markdown to stdout."""
        results_dir = _make_results_dir(tmp_path)
        tier_file = _make_tier_data(tmp_path, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        # Leaderboard contains category headers
        assert "Category 1" in result.output
        assert "Category 2" in result.output

    def test_prints_table_headers(self, tmp_path: Path) -> None:
        """Leaderboard output contains markdown table headers."""
        results_dir = _make_results_dir(tmp_path)
        tier_file = _make_tier_data(tmp_path, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        assert "| Rank | Model |" in result.output
        assert "|---" in result.output


class TestScoreCommandOutputFiles:
    """Test that score command writes expected output files."""

    def test_leaderboard_md_written(self, tmp_path: Path) -> None:
        """leaderboard.md is written to results_dir."""
        results_dir = _make_results_dir(tmp_path)
        tier_file = _make_tier_data(tmp_path, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        leaderboard_file = results_dir / "leaderboard.md"
        assert leaderboard_file.exists(), "leaderboard.md was not written"
        content = leaderboard_file.read_text()
        assert "Category 1" in content

    def test_summary_json_written(self, tmp_path: Path) -> None:
        """summary.json is written to results_dir."""
        results_dir = _make_results_dir(tmp_path)
        tier_file = _make_tier_data(tmp_path, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        summary_file = results_dir / "summary.json"
        assert summary_file.exists(), "summary.json was not written"
        data = json.loads(summary_file.read_text())
        assert isinstance(data, dict)

    def test_prints_written_paths(self, tmp_path: Path) -> None:
        """Score command prints paths to written files."""
        results_dir = _make_results_dir(tmp_path)
        tier_file = _make_tier_data(tmp_path, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        assert "leaderboard.md" in result.output
        assert "summary.json" in result.output


class TestScoreCommandTierData:
    """Test custom tier-data loading."""

    def test_custom_tier_data_path(self, tmp_path: Path) -> None:
        """With custom --tier-data path, tier data is loaded from that file."""
        results_dir = _make_results_dir(tmp_path)
        # Place tier file in a custom location
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        tier_file = _make_tier_data(custom_dir, ["card-001", "card-002"])

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        assert "Category 1" in result.output

    def test_nonexistent_tier_data_path_errors(self, tmp_path: Path) -> None:
        """Missing tier data file produces a non-zero exit or error message."""
        results_dir = _make_results_dir(tmp_path)
        fake_tier = tmp_path / "nonexistent.json"

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(fake_tier)],
        )
        # Should fail since tier data file doesn't exist
        assert result.exit_code != 0


class TestScoreCommandEdgeCases:
    """Edge cases for the score command."""

    def test_empty_results_json(self, tmp_path: Path) -> None:
        """Empty results.json (empty list) produces exit 0 with empty leaderboard."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        (results_dir / "results.json").write_text("[]")
        tier_file = _make_tier_data(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        assert result.exit_code == 0
        # Should still have category headers even with no agents
        assert "Category 1" in result.output

    def test_no_results_json_errors(self, tmp_path: Path) -> None:
        """Missing results.json in results_dir produces empty scores or error."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        tier_file = _make_tier_data(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir), "--tier-data", str(tier_file)],
        )
        # With no results.json and no JSON files, compute_scores gets empty list
        # Should still exit 0 with empty leaderboard
        assert result.exit_code == 0
        assert "Category 1" in result.output

    def test_default_set_code(self, tmp_path: Path, monkeypatch) -> None:
        """Default --set is 'sos' and resolves tier data from _BENCHMARKS_DIR."""
        results_dir = _make_results_dir(tmp_path)

        # Create a fake benchmarks dir under tmp_path so we never touch the repo tree
        fake_benchmarks = tmp_path / "benchmarks"
        default_tier_path = fake_benchmarks / "sos" / "data" / "sos_classified.json"
        default_tier_path.parent.mkdir(parents=True, exist_ok=True)
        entries = [
            {"collector_number": "card-001", "tier": "simple", "name": "Card 1"},
            {"collector_number": "card-002", "tier": "medium", "name": "Card 2"},
        ]
        default_tier_path.write_text(json.dumps(entries))

        # Monkeypatch _BENCHMARKS_DIR so the CLI resolves from our temp dir
        monkeypatch.setattr("benchmark.cli._BENCHMARKS_DIR", fake_benchmarks)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["score", "--results-dir", str(results_dir)],
        )
        assert result.exit_code == 0
        assert "Category 1" in result.output
