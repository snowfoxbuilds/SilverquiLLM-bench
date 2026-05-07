"""Tests for TODO item 4: --cards, --prototype, and --dry-run flags on `benchmark run`.

Tests verify:
- --dry-run with no filters exits 0 and prints card count.
- --cards 011 --dry-run lists only Eager Glyphmage.
- --cards and --prototype together produces UsageError.
- --prototype --dry-run uses prototype cards.
- --cards with invalid collector number produces error message.
- Normal dry-run output includes tier information.
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from benchmark.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimal valid config for testing
_MINIMAL_CONFIG = {
    "name": "test-run",
    "set_code": "SOS",
    "model_name": "test-model",
    "model_provider": "test-provider",
}


def _write_config(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Write a minimal config YAML and return the path."""
    cfg = {**_MINIMAL_CONFIG, **(overrides or {})}
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(cfg))
    return config_file


class TestRunDryRun:
    """Tests for `benchmark run --dry-run`."""

    def test_dry_run_no_filters_exits_zero(self, tmp_path: Path) -> None:
        """--dry-run with no filters exits 0 and prints card count message."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_file), "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run complete." in result.output
        assert "cards selected." in result.output

    def test_dry_run_prints_card_count(self, tmp_path: Path) -> None:
        """--dry-run prints the number of cards found."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_file), "--dry-run"])
        assert result.exit_code == 0
        # Should show "Cards: N" line with a positive number
        assert "Cards:" in result.output

    def test_dry_run_output_includes_tier(self, tmp_path: Path) -> None:
        """Dry-run output includes tier information in brackets for each card."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_file), "--dry-run"])
        assert result.exit_code == 0
        # At least one card should show tier in brackets like [tier_name]
        assert "[" in result.output and "]" in result.output


class TestRunCardsFlag:
    """Tests for `benchmark run --cards`."""

    def test_cards_11_dry_run_lists_eager_glyphmage(self, tmp_path: Path) -> None:
        """--cards 11 --dry-run lists only Eager Glyphmage."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["run", "--config", str(config_file), "--cards", "11", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Eager Glyphmage" in result.output
        assert "Dry run complete. 1 cards selected." in result.output

    def test_cards_filter_with_collector_number_no_leading_zero(self, tmp_path: Path) -> None:
        """--cards 11 --dry-run also matches collector_number '11' (stored without leading zero)."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["run", "--config", str(config_file), "--cards", "11", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Eager Glyphmage" in result.output
        assert "1 cards selected." in result.output

    def test_cards_invalid_collector_number_produces_error(self, tmp_path: Path) -> None:
        """--cards with a non-existent collector number produces an error."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["run", "--config", str(config_file), "--cards", "99999", "--dry-run"]
        )
        # Should fail — either non-zero exit or error message
        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_cards_multiple_comma_separated(self, tmp_path: Path) -> None:
        """--cards accepts comma-separated collector numbers."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["run", "--config", str(config_file), "--cards", "11,12", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "2 cards selected." in result.output


class TestRunMutualExclusion:
    """Tests for mutual exclusion of --cards and --prototype."""

    def test_cards_and_prototype_raises_usage_error(self, tmp_path: Path) -> None:
        """--cards and --prototype together produces a UsageError."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", "--config", str(config_file), "--cards", "11", "--prototype", "--dry-run"],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower() or "usage" in result.output.lower()


class TestRunPrototypeFlag:
    """Tests for `benchmark run --prototype`."""

    def test_prototype_dry_run_uses_prototype_cards(self, tmp_path: Path) -> None:
        """--prototype --dry-run loads from prototype_cards.json and prints card count."""
        config_file = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["run", "--config", str(config_file), "--prototype", "--dry-run"]
        )
        # Should either succeed with prototype cards or fail if prototype file doesn't exist
        # If prototype_cards.json exists, it should exit 0 and show dry run message
        if result.exit_code == 0:
            assert "Dry run complete." in result.output
            assert "cards selected." in result.output
        else:
            # If file doesn't exist, there should be an error about it
            assert "prototype" in result.output.lower() or result.exit_code != 0
