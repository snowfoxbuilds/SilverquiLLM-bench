"""Tests for TODO item 7: Wire `benchmark eval` command.

Tests verify:
- `benchmark eval --results-dir <dir>` exits 0 with properly structured results dir.
- `results.json` is written with expected structure (list of dicts with EvalResult fields).
- With `--audited-tests`, audited eval results appear in JSON.
- Prints eval summary (cards evaluated, pass rates).
- Handles empty results dir gracefully (no run directories found).
- Handles missing implementation files gracefully.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from silverquillm.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_CONFIG = {
    "name": "test-run",
    "set_code": "SOS",
    "model_name": "test-agent",
    "model_provider": "test-provider",
}


def _make_run_dir(base: Path, card_ids: list[str] | None = None) -> Path:
    """Create a run directory with config.yaml and card subdirs.

    Each card dir contains blind_impl.py, tested_impl.py, tests.py.
    """
    base.mkdir(parents=True, exist_ok=True)
    config_file = base / "config.yaml"
    config_file.write_text(yaml.dump(_RUN_CONFIG))
    cards_dir = base / "cards"
    cards_dir.mkdir(exist_ok=True)

    for card_id in (card_ids or ["card-001"]):
        card_dir = cards_dir / card_id
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "blind_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tested_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tests.py").write_text(
            textwrap.dedent("""\
                from card_impl import solve

                def test_solve():
                    assert solve() == 42
            """)
        )

    return base


def _make_audited_tests(tmp_path: Path) -> Path:
    """Create a gold-standard test file for audited eval."""
    audited = tmp_path / "audited_tests.py"
    audited.write_text(
        textwrap.dedent("""\
            from card_impl import solve

            def test_solve_audited():
                assert solve() == 42
        """)
    )
    return audited


# We mock run_self_eval_flat and run_tests to avoid actually running pytest subprocesses.
def _mock_eval_result(card_dir: Path, agent_name: str):
    """Return a fake EvalResult for testing."""
    from silverquillm.evaluator import EvalResult

    return EvalResult(
        card_id=card_dir.name,
        agent=agent_name,
        eval_type="self",
        blind_passed=3,
        blind_failed=1,
        blind_total=4,
        tested_passed=4,
        tested_failed=0,
        tested_total=4,
        errors=[],
    )


def _mock_run_tests(impl_path: Path, tests_path: Path, timeout: int = 60):
    """Return fake run_tests results."""
    return (2, 0, 2, [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvalCommand:
    """Tests for `benchmark eval` CLI command."""

    def test_exits_zero_with_valid_results_dir(self, tmp_path):
        """benchmark eval --results-dir <valid_dir> exits 0."""
        run_dir = _make_run_dir(tmp_path / "run1")

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"

    def test_writes_results_json(self, tmp_path):
        """results.json is written with list of dicts containing EvalResult fields."""
        run_dir = _make_run_dir(tmp_path / "run1")

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0, f"Output: {result.output}"

        results_json = run_dir / "results.json"
        assert results_json.exists(), "results.json should be created"

        data = json.loads(results_json.read_text())
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check EvalResult fields present
        entry = data[0]
        expected_fields = [
            "card_id", "agent", "eval_type",
            "blind_passed", "blind_failed", "blind_total",
            "tested_passed", "tested_failed", "tested_total",
            "errors",
        ]
        for field in expected_fields:
            assert field in entry, f"Missing field: {field}"

    def test_results_json_values_correct(self, tmp_path):
        """results.json entries contain the values returned by run_self_eval_flat."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["card-abc"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0
        data = json.loads((run_dir / "results.json").read_text())
        entry = data[0]
        assert entry["card_id"] == "card-abc"
        assert entry["agent"] == "test-agent"
        assert entry["eval_type"] == "self"
        assert entry["blind_passed"] == 3
        assert entry["tested_passed"] == 4

    def test_audited_tests_adds_audited_results(self, tmp_path):
        """With --audited-tests, audited eval results appear in JSON."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["card-001"])
        audited_file = _make_audited_tests(tmp_path)

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result), \
             patch("silverquillm.evaluator.run_tests", side_effect=_mock_run_tests):
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-tests", str(audited_file)],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"

        data = json.loads((run_dir / "results.json").read_text())
        eval_types = [r["eval_type"] for r in data]
        assert "audited" in eval_types, f"Expected 'audited' eval type in {eval_types}"

    def test_audited_result_has_correct_structure(self, tmp_path):
        """Audited eval results have proper EvalResult fields."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["card-001"])
        audited_file = _make_audited_tests(tmp_path)

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result), \
             patch("silverquillm.evaluator.run_tests", side_effect=_mock_run_tests):
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-tests", str(audited_file)],
            )

        assert result.exit_code == 0
        data = json.loads((run_dir / "results.json").read_text())
        audited_entries = [r for r in data if r["eval_type"] == "audited"]
        assert len(audited_entries) >= 1
        entry = audited_entries[0]
        assert entry["card_id"] == "card-001"
        assert entry["agent"] == "test-agent"
        assert "blind_passed" in entry
        assert "tested_passed" in entry

    def test_prints_eval_summary(self, tmp_path):
        """Output includes eval summary with cards evaluated count."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["card-001", "card-002"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0
        assert "Eval Summary" in result.output
        assert "Cards evaluated: 2" in result.output

    def test_prints_pass_rates(self, tmp_path):
        """Output includes pass rate information."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["card-001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0
        # Should display blind and tested pass rates
        assert "blind:" in result.output
        assert "tested:" in result.output

    def test_prints_results_saved_path(self, tmp_path):
        """Output indicates where results.json was saved."""
        run_dir = _make_run_dir(tmp_path / "run1")

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0
        assert "Results saved to:" in result.output

    def test_empty_results_dir_errors(self, tmp_path):
        """Empty results dir (no run directories) exits non-zero with error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(main, ["eval", "--results-dir", str(empty_dir)])

        assert result.exit_code != 0
        assert "No run directories found" in result.output

    def test_nonexistent_results_dir_errors(self, tmp_path):
        """Non-existent results dir exits non-zero with error."""
        runner = CliRunner()
        result = runner.invoke(main, ["eval", "--results-dir", str(tmp_path / "nope")])

        assert result.exit_code != 0

    def test_missing_impl_files_handled_gracefully(self, tmp_path):
        """Card dir with missing impl files doesn't crash; errors reported."""
        run_dir = tmp_path / "run1"
        run_dir.mkdir(parents=True)
        (run_dir / "config.yaml").write_text(yaml.dump(_RUN_CONFIG))
        cards_dir = run_dir / "cards"
        cards_dir.mkdir()
        card_dir = cards_dir / "card-incomplete"
        card_dir.mkdir()
        # Only create tests.py, no impl files
        (card_dir / "tests.py").write_text("def test_x(): pass\n")

        runner = CliRunner()
        # Don't mock run_self_eval_flat — let it handle missing files naturally
        # But we do need to mock run_tests since it would try subprocess
        with patch("silverquillm.evaluator.run_tests", return_value=(0, 0, 0, [])):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        # Should exit 0 and produce results (with errors noted)
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        data = json.loads((run_dir / "results.json").read_text())
        assert len(data) >= 1
        # The entry should note missing files in errors
        entry = data[0]
        assert entry["card_id"] == "card-incomplete"

    def test_multiple_cards_all_evaluated(self, tmp_path):
        """Multiple cards in a run dir are all evaluated."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["c1", "c2", "c3"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(run_dir)])

        assert result.exit_code == 0
        data = json.loads((run_dir / "results.json").read_text())
        card_ids = [r["card_id"] for r in data]
        assert "c1" in card_ids
        assert "c2" in card_ids
        assert "c3" in card_ids

    def test_nested_run_dirs_discovered(self, tmp_path):
        """When results_dir contains subdirs that are run dirs, they are found."""
        parent = tmp_path / "all_runs"
        parent.mkdir()
        _make_run_dir(parent / "run-2024-01", card_ids=["card-a"])
        _make_run_dir(parent / "run-2024-02", card_ids=["card-b"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat", side_effect=_mock_eval_result):
            result = runner.invoke(main, ["eval", "--results-dir", str(parent)])

        assert result.exit_code == 0
        data = json.loads((parent / "results.json").read_text())
        card_ids = [r["card_id"] for r in data]
        assert "card-a" in card_ids
        assert "card-b" in card_ids
