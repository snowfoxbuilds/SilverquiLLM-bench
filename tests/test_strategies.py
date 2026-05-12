"""Tests for TODO item 1: mode field on BenchmarkConfig and CardStrategy ABC.

Tests verify:
- BenchmarkConfig has a ``mode`` field defaulting to ``"impl_test"``.
- load_config() parses ``mode`` from YAML, defaults to ``"impl_test"``, rejects invalid values.
- max_test_rounds removed from AgentConfig (no longer used).
- CardStrategy ABC exists with abstract ``run_card`` method.
- CardRunResult dataclass has expected fields and types.
- CardRunStatus enum has expected members.
- get_strategy() returns correct strategy subclass for each valid mode.
- get_strategy() raises ValueError for unknown modes.
"""

from __future__ import annotations

import textwrap
from abc import ABC
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from silverquillm.config import AgentConfig, BenchmarkConfig, load_config
from silverquillm.strategies import (
    BlindStrategy,
    CardRunResult,
    CardRunStatus,
    CardStrategy,
    ImplTestStrategy,
    get_strategy,
)

# Minimal valid YAML keys for BenchmarkConfig.
_MINIMAL_RAW = {
    "name": "test-run",
    "set_code": "SOS",
    "model_name": "test-model",
    "model_provider": "test-provider",
}


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


# =========================================================================
# BenchmarkConfig.mode field
# =========================================================================
class TestBenchmarkConfigMode:
    """Tests for the mode field on BenchmarkConfig."""

    def test_default_mode_is_impl_test(self) -> None:
        """When mode is not specified, it should default to 'impl_test'."""
        cfg = BenchmarkConfig(**_MINIMAL_RAW)
        assert cfg.mode == "impl_test"

    def test_mode_blind_accepted(self) -> None:
        """'blind' is a valid mode value."""
        cfg = BenchmarkConfig(**_MINIMAL_RAW, mode="blind")
        assert cfg.mode == "blind"

    def test_mode_impl_test_accepted(self) -> None:
        """'impl_test' is a valid mode value."""
        cfg = BenchmarkConfig(**_MINIMAL_RAW, mode="impl_test")
        assert cfg.mode == "impl_test"

    def test_invalid_mode_raises_value_error(self) -> None:
        """An invalid mode value should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            BenchmarkConfig(**_MINIMAL_RAW, mode="invalid_mode")

    def test_empty_string_mode_raises_value_error(self) -> None:
        """An empty string mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            BenchmarkConfig(**_MINIMAL_RAW, mode="")


# =========================================================================
# load_config() — mode parsing
# =========================================================================
class TestLoadConfigMode:
    """Tests for load_config() parsing of the mode field."""

    def test_mode_parsed_from_yaml(self, tmp_path: Path) -> None:
        """load_config should read mode from YAML."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            mode: "blind"
        """)
        cfg = load_config(str(p))
        assert cfg.mode == "blind"

    def test_mode_defaults_to_impl_test_when_absent(self, tmp_path: Path) -> None:
        """When mode is not in YAML, it should default to 'impl_test' for backward compat."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
        """)
        cfg = load_config(str(p))
        assert cfg.mode == "impl_test"

    def test_invalid_mode_in_yaml_raises(self, tmp_path: Path) -> None:
        """load_config should reject YAML with an invalid mode value."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            mode: "turbo"
        """)
        with pytest.raises(ValueError, match="Invalid mode"):
            load_config(str(p))

    def test_mode_impl_test_explicit_in_yaml(self, tmp_path: Path) -> None:
        """Explicitly specifying impl_test in YAML should work."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            mode: "impl_test"
        """)
        cfg = load_config(str(p))
        assert cfg.mode == "impl_test"


# =========================================================================
# max_test_rounds removal from AgentConfig
# =========================================================================
class TestMaxTestRoundsRemoved:
    """max_test_rounds should no longer be a field on AgentConfig."""

    def test_agent_config_has_no_max_test_rounds(self) -> None:
        """AgentConfig should not have a max_test_rounds field."""
        field_names = {f.name for f in dc_fields(AgentConfig)}
        assert "max_test_rounds" not in field_names


# =========================================================================
# CardRunStatus enum
# =========================================================================
class TestCardRunStatus:
    """Tests for the CardRunStatus enum."""

    def test_has_completed(self) -> None:
        assert CardRunStatus.completed.value == "completed"

    def test_has_timeout(self) -> None:
        assert CardRunStatus.timeout.value == "timeout"

    def test_has_no_output(self) -> None:
        assert CardRunStatus.no_output.value == "no_output"

    def test_exactly_three_members(self) -> None:
        """CardRunStatus should have exactly 3 members."""
        assert len(CardRunStatus) == 3


# =========================================================================
# CardRunResult dataclass
# =========================================================================
class TestCardRunResult:
    """Tests for the CardRunResult dataclass."""

    def test_has_expected_fields(self) -> None:
        names = {f.name for f in dc_fields(CardRunResult)}
        assert names == {"status", "files_written", "runtime_ms", "engine_modified"}

    def test_defaults(self) -> None:
        """files_written defaults to empty list, runtime_ms to 0, engine_modified to False."""
        result = CardRunResult(status=CardRunStatus.completed)
        assert result.files_written == []
        assert result.runtime_ms == 0
        assert result.engine_modified is False

    def test_custom_values(self) -> None:
        result = CardRunResult(
            status=CardRunStatus.timeout,
            files_written=[Path("a.py"), Path("b.py")],
            runtime_ms=1500,
            engine_modified=True,
        )
        assert result.status == CardRunStatus.timeout
        assert len(result.files_written) == 2
        assert result.runtime_ms == 1500
        assert result.engine_modified is True


# =========================================================================
# CardStrategy ABC
# =========================================================================
class TestCardStrategyABC:
    """Tests for the CardStrategy abstract base class."""

    def test_is_abstract_class(self) -> None:
        assert issubclass(CardStrategy, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """CardStrategy should not be instantiatable because run_card is abstract."""
        with pytest.raises(TypeError):
            CardStrategy()

    def test_run_card_is_abstract(self) -> None:
        """run_card should be declared as an abstract method."""
        assert getattr(CardStrategy.run_card, "__isabstractmethod__", False)

    def test_blind_strategy_is_subclass(self) -> None:
        assert issubclass(BlindStrategy, CardStrategy)

    def test_impl_test_strategy_is_subclass(self) -> None:
        assert issubclass(ImplTestStrategy, CardStrategy)


# =========================================================================
# get_strategy() factory
# =========================================================================
class TestGetStrategy:
    """Tests for the get_strategy() factory function."""

    def test_blind_returns_blind_strategy(self) -> None:
        strategy = get_strategy("blind")
        assert isinstance(strategy, BlindStrategy)

    def test_impl_test_returns_impl_test_strategy(self) -> None:
        strategy = get_strategy("impl_test")
        assert isinstance(strategy, ImplTestStrategy)

    def test_unknown_mode_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown mode"):
            get_strategy("unknown")

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_strategy("")

    def test_returns_new_instance_each_call(self) -> None:
        """Each call should return a fresh instance."""
        s1 = get_strategy("blind")
        s2 = get_strategy("blind")
        assert s1 is not s2


# =========================================================================
# config.example.yaml includes mode
# =========================================================================
class TestConfigExampleYaml:
    """Verify config.example.yaml has been updated with the mode field."""

    def test_example_yaml_has_mode_field(self) -> None:
        example = Path(__file__).resolve().parent.parent / "config.example.yaml"
        if not example.exists():
            pytest.skip("config.example.yaml not found")
        content = example.read_text()
        assert "mode:" in content

    def test_example_yaml_loads_with_valid_mode(self) -> None:
        example = Path(__file__).resolve().parent.parent / "config.example.yaml"
        if not example.exists():
            pytest.skip("config.example.yaml not found")
        cfg = load_config(str(example))
        assert cfg.mode in ("blind", "impl_test")
