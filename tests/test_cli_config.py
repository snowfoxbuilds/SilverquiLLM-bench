"""Tests for TODO item 9: Runner CLI scaffold + YAML config.

Tests verify:
- CLI help output (--help) works for main command and each subcommand.
- ``benchmark cards --set SOS`` lists cards with tiers.
- ``load_config`` loads valid YAML and returns BenchmarkConfig.
- ``load_config`` raises ValueError on missing required fields.
- ``load_config`` uses defaults for optional fields.
- ``config.example.yaml`` exists and is valid YAML that loads successfully.
- BenchmarkConfig has all expected fields.
- ``benchmark run`` stub loads config correctly.
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.config import BenchmarkConfig, load_config

REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimal valid config dict (all required fields)
_MINIMAL_CONFIG = {
    "name": "test-run",
    "set_code": "SOS",
    "model_name": "test-model",
    "model_provider": "test-provider",
}


# ---------------------------------------------------------------------------
# BenchmarkConfig dataclass
# ---------------------------------------------------------------------------
class TestBenchmarkConfig:
    """Tests for the BenchmarkConfig dataclass."""

    def test_has_required_fields(self) -> None:
        """BenchmarkConfig has the four required fields: name, set_code, model_name, model_provider."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.name == "test-run"
        assert cfg.set_code == "SOS"
        assert cfg.model_name == "test-model"
        assert cfg.model_provider == "test-provider"

    def test_has_optional_fields_with_defaults(self) -> None:
        """BenchmarkConfig exposes optional fields with sensible defaults."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert isinstance(cfg.max_context, int)
        assert isinstance(cfg.temperature, (int, float))
        assert isinstance(cfg.agent_tool, str)
        assert isinstance(cfg.max_test_rounds, int)
        assert isinstance(cfg.timeout_per_card, int)
        assert isinstance(cfg.disable_web_search, bool)

    def test_default_max_context(self) -> None:
        """max_context defaults to 200_000."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.max_context == 200_000

    def test_default_temperature(self) -> None:
        """temperature defaults to 0.0."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.temperature == 0.0

    def test_default_max_test_rounds(self) -> None:
        """max_test_rounds defaults to 3."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.max_test_rounds == 3

    def test_default_timeout_per_card(self) -> None:
        """timeout_per_card defaults to 300."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.timeout_per_card == 300

    def test_default_disable_web_search(self) -> None:
        """disable_web_search defaults to True."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.disable_web_search is True

    def test_default_agent_tool(self) -> None:
        """agent_tool defaults to 'opencode'."""
        cfg = BenchmarkConfig(**_MINIMAL_CONFIG)
        assert cfg.agent_tool == "opencode"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------
class TestLoadConfig:
    """Tests for the load_config function."""

    def _write_yaml(self, tmp_path: Path, data: dict) -> Path:
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        return p

    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        """load_config returns a BenchmarkConfig from valid YAML."""
        p = self._write_yaml(tmp_path, _MINIMAL_CONFIG)
        cfg = load_config(str(p))
        assert isinstance(cfg, BenchmarkConfig)
        assert cfg.name == "test-run"

    def test_raises_on_missing_required_name(self, tmp_path: Path) -> None:
        """load_config raises ValueError when 'name' is missing."""
        data = {**_MINIMAL_CONFIG}
        del data["name"]
        p = self._write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="name"):
            load_config(str(p))

    def test_raises_on_missing_required_set_code(self, tmp_path: Path) -> None:
        """load_config raises ValueError when 'set_code' is missing."""
        data = {**_MINIMAL_CONFIG}
        del data["set_code"]
        p = self._write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="set_code"):
            load_config(str(p))

    def test_raises_on_missing_required_model_name(self, tmp_path: Path) -> None:
        """load_config raises ValueError when 'model_name' is missing."""
        data = {**_MINIMAL_CONFIG}
        del data["model_name"]
        p = self._write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="model_name"):
            load_config(str(p))

    def test_raises_on_missing_required_model_provider(self, tmp_path: Path) -> None:
        """load_config raises ValueError when 'model_provider' is missing."""
        data = {**_MINIMAL_CONFIG}
        del data["model_provider"]
        p = self._write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="model_provider"):
            load_config(str(p))

    def test_raises_on_empty_yaml(self, tmp_path: Path) -> None:
        """load_config raises ValueError on empty YAML file."""
        p = tmp_path / "empty.yaml"
        p.write_text("")
        with pytest.raises(ValueError):
            load_config(str(p))

    def test_raises_on_nonexistent_file(self) -> None:
        """load_config raises FileNotFoundError for a missing path."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_optional_fields_use_defaults(self, tmp_path: Path) -> None:
        """When optional fields are omitted, defaults are used."""
        p = self._write_yaml(tmp_path, _MINIMAL_CONFIG)
        cfg = load_config(str(p))
        assert cfg.max_context == 200_000
        assert cfg.temperature == 0.0
        assert cfg.max_test_rounds == 3

    def test_override_optional_fields(self, tmp_path: Path) -> None:
        """Optional fields can be overridden via YAML."""
        data = {**_MINIMAL_CONFIG, "max_context": 100_000, "temperature": 0.5}
        p = self._write_yaml(tmp_path, data)
        cfg = load_config(str(p))
        assert cfg.max_context == 100_000
        assert cfg.temperature == 0.5

    def test_ignores_unknown_fields(self, tmp_path: Path) -> None:
        """Unknown YAML keys are silently ignored."""
        data = {**_MINIMAL_CONFIG, "unknown_key": "whatever"}
        p = self._write_yaml(tmp_path, data)
        cfg = load_config(str(p))
        assert not hasattr(cfg, "unknown_key")


# ---------------------------------------------------------------------------
# config.example.yaml
# ---------------------------------------------------------------------------
class TestExampleConfig:
    """Tests for the config.example.yaml file in the repo root."""

    def test_example_yaml_exists(self) -> None:
        """config.example.yaml exists at repo root."""
        assert (REPO_ROOT / "config.example.yaml").exists()

    def test_example_yaml_is_valid(self) -> None:
        """config.example.yaml can be parsed as YAML."""
        with open(REPO_ROOT / "config.example.yaml") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_example_yaml_loads_as_config(self) -> None:
        """config.example.yaml loads successfully via load_config."""
        cfg = load_config(str(REPO_ROOT / "config.example.yaml"))
        assert isinstance(cfg, BenchmarkConfig)
        assert cfg.name  # non-empty
        assert cfg.set_code  # non-empty


# ---------------------------------------------------------------------------
# CLI --help
# ---------------------------------------------------------------------------
class TestCLIHelp:
    """Tests for CLI help output."""

    def test_main_help(self) -> None:
        """``benchmark --help`` exits 0 and prints usage."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output or "usage" in result.output.lower()

    def test_run_help(self) -> None:
        """``benchmark run --help`` exits 0."""
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_eval_help(self) -> None:
        """``benchmark eval --help`` exits 0."""
        runner = CliRunner()
        result = runner.invoke(main, ["eval", "--help"])
        assert result.exit_code == 0

    def test_score_help(self) -> None:
        """``benchmark score --help`` exits 0."""
        runner = CliRunner()
        result = runner.invoke(main, ["score", "--help"])
        assert result.exit_code == 0

    def test_cards_help(self) -> None:
        """``benchmark cards --help`` exits 0."""
        runner = CliRunner()
        result = runner.invoke(main, ["cards", "--help"])
        assert result.exit_code == 0
        assert "set" in result.output.lower()


# ---------------------------------------------------------------------------
# CLI cards subcommand
# ---------------------------------------------------------------------------
class TestCLICards:
    """Tests for ``benchmark cards --set <code>``."""

    def test_cards_set_sos_lists_cards(self) -> None:
        """``benchmark cards --set SOS`` lists cards with tier labels."""
        runner = CliRunner()
        result = runner.invoke(main, ["cards", "--set", "SOS"])
        # Should succeed
        assert result.exit_code == 0
        # Output should mention total count
        assert "Cards in set SOS" in result.output
        # Should contain tier labels in brackets
        assert "[" in result.output and "]" in result.output

    def test_cards_set_sos_has_tiers(self) -> None:
        """Output from ``cards --set SOS`` includes recognized tier labels."""
        runner = CliRunner()
        result = runner.invoke(main, ["cards", "--set", "SOS"])
        assert result.exit_code == 0
        valid_tiers = {"trivial", "simple", "medium", "complex", "expert"}
        lines = result.output.strip().splitlines()
        # At least some card lines should contain a tier label
        card_lines = [l for l in lines if l.strip().startswith("[")]
        assert len(card_lines) > 0, "Expected card lines with [tier] labels"
        for line in card_lines:
            tier = line.strip().lstrip("[").split("]")[0]
            assert tier in valid_tiers, f"Unexpected tier '{tier}' in line: {line}"

    def test_cards_nonexistent_set_fails(self) -> None:
        """``benchmark cards --set NOSUCH`` reports an error."""
        runner = CliRunner()
        result = runner.invoke(main, ["cards", "--set", "NOSUCH"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI run subcommand
# ---------------------------------------------------------------------------
class TestCLIRun:
    """Tests for ``benchmark run --config <path>``."""

    def test_run_loads_config(self, tmp_path: Path) -> None:
        """``benchmark run --config <valid.yaml>`` loads config and prints name."""
        p = tmp_path / "cfg.yaml"
        p.write_text(yaml.dump(_MINIMAL_CONFIG))
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(p), "--dry-run"])
        assert result.exit_code == 0
        assert "Config loaded" in result.output
        assert "test-run" in result.output

    def test_run_missing_config_fails(self) -> None:
        """``benchmark run --config /no/such/file`` exits with error."""
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", "/no/such/file.yaml"])
        assert result.exit_code != 0
