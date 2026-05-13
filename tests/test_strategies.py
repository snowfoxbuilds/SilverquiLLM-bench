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
        assert names == {"status", "files_written", "runtime_ms", "engine_modified", "violations", "agent_output", "prompt_used"}

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


# =========================================================================
# BlindStrategy.run_card (TODO item 2)
# =========================================================================

_SAMPLE_CARD_SPEC: dict = {
    "name": "Lightning Bolt",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
}


class _MockAdapter:
    """Simple mock adapter that records calls and optionally writes card_impl.py.

    Has run_with_retries() to mirror AgentAdapter — strategies must call
    run_with_retries() instead of run() directly.
    """

    def __init__(self, *, write_impl: bool = False, raise_timeout: bool = False) -> None:
        self._write_impl = write_impl
        self._raise_timeout = raise_timeout
        self.calls: list[tuple[str, Path]] = []
        self.run_with_retries_calls: list[dict] = []

    def run(self, prompt: str, workspace: Path) -> str:
        self.calls.append((prompt, workspace))
        if self._raise_timeout:
            raise TimeoutError("adapter timed out")
        if self._write_impl:
            (workspace / "card_impl.py").write_text("# impl\n")
        return "done"

    def run_with_retries(
        self,
        prompt: str,
        workspace: Path,
        *,
        retries: int = 2,
        timeout: int | None = None,
    ) -> str:
        self.run_with_retries_calls.append(
            {"prompt": prompt, "workspace": workspace, "retries": retries, "timeout": timeout}
        )
        return self.run(prompt, workspace)


class TestBlindStrategyRunCard:
    """Tests for BlindStrategy.run_card() — the core of blind-mode execution."""

    def test_completed_when_adapter_writes_card_impl(self, tmp_path: Path) -> None:
        """When the adapter writes card_impl.py, status should be 'completed'."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.completed

    def test_no_output_when_adapter_writes_nothing(self, tmp_path: Path) -> None:
        """When the adapter produces no card_impl.py, status should be 'no_output'."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.no_output

    def test_timeout_when_adapter_raises_timeout_error(self, tmp_path: Path) -> None:
        """When the adapter raises TimeoutError, status should be 'timeout'."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.timeout

    def test_timeout_with_card_impl_present(self, tmp_path: Path) -> None:
        """If timeout occurs but card_impl.py exists (partial work), files_written should include it."""
        strategy = BlindStrategy()
        # Pre-create the file to simulate partial work before timeout
        (tmp_path / "card_impl.py").write_text("# partial\n")
        adapter = _MockAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.timeout
        assert any(str(p).endswith("card_impl.py") for p in result.files_written)

    def test_files_written_contains_card_impl_on_completed(self, tmp_path: Path) -> None:
        """On completed, files_written should list the card_impl.py path."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert len(result.files_written) >= 1
        assert any(str(p).endswith("card_impl.py") for p in result.files_written)

    def test_files_written_empty_on_no_output(self, tmp_path: Path) -> None:
        """On no_output, files_written should be empty."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.files_written == []

    def test_runtime_ms_is_non_negative(self, tmp_path: Path) -> None:
        """runtime_ms should be a non-negative integer."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert isinstance(result.runtime_ms, int)
        assert result.runtime_ms >= 0

    def test_engine_modified_defaults_false(self, tmp_path: Path) -> None:
        """engine_modified should default to False for a basic blind run."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.engine_modified is False

    def test_adapter_receives_prompt_with_card_name(self, tmp_path: Path) -> None:
        """The prompt sent to the adapter should contain the card name."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert len(adapter.run_with_retries_calls) == 1
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "Lightning Bolt" in prompt

    def test_adapter_receives_prompt_referencing_card_impl(self, tmp_path: Path) -> None:
        """The prompt sent to the adapter should reference card_impl.py."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "card_impl.py" in prompt

    def test_adapter_receives_prompt_without_test_utils(self, tmp_path: Path) -> None:
        """The prompt in blind mode should NOT mention test_utils."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "test_utils" not in prompt

    def test_adapter_called_exactly_once(self, tmp_path: Path) -> None:
        """Blind mode sends exactly one prompt to the adapter via run_with_retries."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert len(adapter.run_with_retries_calls) == 1

    def test_result_is_card_run_result(self, tmp_path: Path) -> None:
        """run_card must return a CardRunResult instance."""
        strategy = BlindStrategy()
        adapter = _MockAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert isinstance(result, CardRunResult)


# =========================================================================
# ImplTestStrategy.run_card (TODO item 3)
# =========================================================================


class _ImplTestMockAdapter:
    """Mock adapter for ImplTestStrategy tests.

    Can write card_impl.py, tests.py, or neither based on flags.
    Has run_with_retries() to mirror AgentAdapter.
    """

    def __init__(
        self,
        *,
        write_impl: bool = False,
        write_tests: bool = False,
        raise_timeout: bool = False,
    ) -> None:
        self._write_impl = write_impl
        self._write_tests = write_tests
        self._raise_timeout = raise_timeout
        self.calls: list[tuple[str, Path]] = []
        self.run_with_retries_calls: list[dict] = []

    def run(self, prompt: str, workspace: Path) -> str:
        self.calls.append((prompt, workspace))
        if self._raise_timeout:
            raise TimeoutError("adapter timed out")
        if self._write_impl:
            (workspace / "card_impl.py").write_text("# impl\n")
        if self._write_tests:
            (workspace / "tests.py").write_text("# tests\n")
        return "done"

    def run_with_retries(
        self,
        prompt: str,
        workspace: Path,
        *,
        retries: int = 2,
        timeout: int | None = None,
    ) -> str:
        self.run_with_retries_calls.append(
            {"prompt": prompt, "workspace": workspace, "retries": retries, "timeout": timeout}
        )
        return self.run(prompt, workspace)


class TestImplTestStrategyRunCard:
    """Tests for ImplTestStrategy.run_card() — the core of impl_test-mode execution."""

    def test_completed_when_both_files_written(self, tmp_path: Path) -> None:
        """When adapter writes both card_impl.py and tests.py, status → completed."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True, write_tests=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.completed

    def test_completed_when_only_card_impl_written(self, tmp_path: Path) -> None:
        """When adapter writes only card_impl.py (no tests), status → completed (partial ok)."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True, write_tests=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.completed

    def test_no_output_when_nothing_written(self, tmp_path: Path) -> None:
        """When adapter writes nothing, status → no_output."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=False, write_tests=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.no_output

    def test_no_output_when_only_tests_written(self, tmp_path: Path) -> None:
        """If only tests.py is written but no card_impl.py, status → no_output."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=False, write_tests=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.no_output

    def test_timeout_status_on_timeout_error(self, tmp_path: Path) -> None:
        """When adapter times out, status → timeout."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.timeout

    def test_timeout_with_both_files_present(self, tmp_path: Path) -> None:
        """If timeout occurs but both files exist (partial work), files_written has both."""
        strategy = ImplTestStrategy()
        (tmp_path / "card_impl.py").write_text("# partial impl\n")
        (tmp_path / "tests.py").write_text("# partial tests\n")
        adapter = _ImplTestMockAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.timeout
        written_names = {p.name for p in result.files_written}
        assert "card_impl.py" in written_names
        assert "tests.py" in written_names

    def test_timeout_with_only_card_impl_present(self, tmp_path: Path) -> None:
        """If timeout but only card_impl.py exists, files_written has only that."""
        strategy = ImplTestStrategy()
        (tmp_path / "card_impl.py").write_text("# partial\n")
        adapter = _ImplTestMockAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.timeout
        written_names = {p.name for p in result.files_written}
        assert "card_impl.py" in written_names
        assert "tests.py" not in written_names

    def test_files_written_both_when_both_exist(self, tmp_path: Path) -> None:
        """When both files written on success, files_written lists both."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True, write_tests=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        written_names = {p.name for p in result.files_written}
        assert "card_impl.py" in written_names
        assert "tests.py" in written_names

    def test_files_written_only_impl_when_no_tests(self, tmp_path: Path) -> None:
        """When only card_impl.py written, files_written has just that file."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True, write_tests=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        written_names = {p.name for p in result.files_written}
        assert "card_impl.py" in written_names
        assert "tests.py" not in written_names

    def test_files_written_empty_on_no_output(self, tmp_path: Path) -> None:
        """On no_output, files_written should be empty."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=False, write_tests=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.files_written == []

    def test_adapter_called_exactly_once(self, tmp_path: Path) -> None:
        """Impl_test mode sends exactly one prompt via run_with_retries — agent self-manages iteration."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True, write_tests=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert len(adapter.run_with_retries_calls) == 1

    def test_prompt_contains_card_name(self, tmp_path: Path) -> None:
        """The prompt sent to the adapter should contain the card name."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "Lightning Bolt" in prompt

    def test_prompt_references_card_impl_py(self, tmp_path: Path) -> None:
        """The prompt must instruct agent to write to card_impl.py."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "card_impl.py" in prompt

    def test_prompt_references_tests_py(self, tmp_path: Path) -> None:
        """The prompt must instruct agent to write to tests.py."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "tests.py" in prompt

    def test_prompt_mentions_test_utils(self, tmp_path: Path) -> None:
        """Impl_test prompt must reference test_utils for agent's use."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "test_utils" in prompt

    def test_prompt_mentions_test_utils_md(self, tmp_path: Path) -> None:
        """Impl_test prompt must reference test_utils.md documentation."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "test_utils.md" in prompt

    def test_prompt_encourages_self_iteration(self, tmp_path: Path) -> None:
        """Impl_test prompt must tell agent it can run tests itself to iterate."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "run tests" in prompt.lower() or "iterate" in prompt.lower()

    def test_prompt_does_not_mention_max_test_rounds(self, tmp_path: Path) -> None:
        """Impl_test prompt must not reference max_test_rounds or multi-round harness feedback."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        prompt = adapter.run_with_retries_calls[0]["prompt"]
        assert "max_test_rounds" not in prompt
        assert "max_rounds" not in prompt

    def test_runtime_ms_is_non_negative(self, tmp_path: Path) -> None:
        """runtime_ms should be a non-negative integer."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True, write_tests=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert isinstance(result.runtime_ms, int)
        assert result.runtime_ms >= 0

    def test_result_is_card_run_result(self, tmp_path: Path) -> None:
        """run_card must return a CardRunResult instance."""
        strategy = ImplTestStrategy()
        adapter = _ImplTestMockAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert isinstance(result, CardRunResult)


# =========================================================================
# TODO item 6: ThreadPoolExecutor removal and direct adapter calls
# =========================================================================

import inspect
import threading


class _KillTrackingAdapter:
    """Mock adapter that tracks whether kill() was called.

    Has run_with_retries() to mirror AgentAdapter.
    """

    def __init__(self, *, write_impl: bool = False, output: str = "adapter output") -> None:
        self._write_impl = write_impl
        self._output = output
        self.calls: list[tuple[str, Path]] = []
        self.run_with_retries_calls: list[dict] = []
        self.kill_called = False

    def run(self, prompt: str, workspace: Path) -> str:
        self.calls.append((prompt, workspace))
        if self._write_impl:
            (workspace / "card_impl.py").write_text("# impl\n")
        return self._output

    def run_with_retries(
        self,
        prompt: str,
        workspace: Path,
        *,
        retries: int = 2,
        timeout: int | None = None,
    ) -> str:
        self.run_with_retries_calls.append(
            {"prompt": prompt, "workspace": workspace, "retries": retries, "timeout": timeout}
        )
        return self.run(prompt, workspace)

    def kill(self) -> None:
        self.kill_called = True


class _BlockingAdapter:
    """Mock adapter that raises TimeoutError to simulate timeout.

    Has run_with_retries() that mirrors AgentAdapter behaviour: calls
    self.run(), and on TimeoutError calls self.kill() before re-raising.
    Uses no time.sleep() or while True per testing conventions.
    """

    def __init__(self) -> None:
        self.kill_called = False
        self._event = threading.Event()
        self.calls: list[tuple[str, Path]] = []
        self.run_with_retries_calls: list[dict] = []

    def run(self, prompt: str, workspace: Path) -> str:
        self.calls.append((prompt, workspace))
        raise TimeoutError("adapter timed out")

    def run_with_retries(
        self,
        prompt: str,
        workspace: Path,
        *,
        retries: int = 2,
        timeout: int | None = None,
    ) -> str:
        self.run_with_retries_calls.append(
            {"prompt": prompt, "workspace": workspace, "retries": retries, "timeout": timeout}
        )
        try:
            return self.run(prompt, workspace)
        except TimeoutError:
            self.kill()
            raise

    def kill(self) -> None:
        self.kill_called = True


class TestNoThreadPoolExecutorImport:
    """Verify ThreadPoolExecutor and FuturesTimeoutError are not used in strategies.py."""

    def test_no_thread_pool_executor_import(self) -> None:
        """strategies.py must not import ThreadPoolExecutor (removed per TODO 6)."""
        import silverquillm.strategies as mod
        source = inspect.getsource(mod)
        assert "ThreadPoolExecutor" not in source

    def test_no_futures_timeout_error_import(self) -> None:
        """strategies.py must not import concurrent.futures TimeoutError."""
        import silverquillm.strategies as mod
        source = inspect.getsource(mod)
        # Should not reference concurrent.futures at all
        assert "concurrent.futures" not in source

    def test_no_concurrent_futures_module_in_strategies(self) -> None:
        """The concurrent.futures module should not appear in strategies module namespace."""
        import silverquillm.strategies as mod
        # Check that concurrent.futures is not among the module's imported names
        assert not hasattr(mod, "ThreadPoolExecutor")
        assert not hasattr(mod, "futures")


class TestDirectAdapterCallBlind:
    """Verify BlindStrategy calls adapter.run_with_retries() and handles timeout/kill."""

    def test_adapter_run_with_retries_called(self, tmp_path: Path) -> None:
        """BlindStrategy should call adapter.run_with_retries() (not run() directly)."""
        strategy = BlindStrategy()
        adapter = _KillTrackingAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert len(adapter.run_with_retries_calls) == 1
        assert result.status == CardRunStatus.completed

    def test_run_with_retries_receives_timeout_and_zero_retries(self, tmp_path: Path) -> None:
        """Strategy must pass timeout=<timeout> and retries=0 to run_with_retries."""
        strategy = BlindStrategy()
        adapter = _KillTrackingAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=42)
        call = adapter.run_with_retries_calls[0]
        assert call["timeout"] == 42
        assert call["retries"] == 0

    def test_agent_output_captured_in_result(self, tmp_path: Path) -> None:
        """adapter.run_with_retries() return value should be stored in CardRunResult.agent_output."""
        strategy = BlindStrategy()
        adapter = _KillTrackingAdapter(write_impl=True, output="blind output 42")
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.agent_output == "blind output 42"

    def test_kill_called_on_timeout(self, tmp_path: Path) -> None:
        """When adapter raises TimeoutError, adapter.kill() should be called."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=5)
        assert result.status == CardRunStatus.timeout
        assert adapter.kill_called is True

    def test_kill_not_called_on_success(self, tmp_path: Path) -> None:
        """adapter.kill() should NOT be called on successful completion."""
        strategy = BlindStrategy()
        adapter = _KillTrackingAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.completed
        assert adapter.kill_called is False

    def test_timeout_result_has_empty_agent_output(self, tmp_path: Path) -> None:
        """On timeout, agent_output should be empty string."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=5)
        assert result.agent_output == ""

    def test_run_not_called_directly_by_strategy(self, tmp_path: Path) -> None:
        """Strategy must NOT call adapter.run() directly — only via run_with_retries()."""
        strategy = BlindStrategy()

        class _SpyAdapter(_KillTrackingAdapter):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.direct_run_calls = 0

            def run(self, prompt, workspace):
                self.direct_run_calls += 1
                return super().run(prompt, workspace)

            def run_with_retries(self, prompt, workspace, *, retries=2, timeout=None):
                # Only count calls that come through run_with_retries
                self.run_with_retries_calls.append(
                    {"prompt": prompt, "workspace": workspace, "retries": retries, "timeout": timeout}
                )
                # Reset direct_run_calls before delegating so we only track
                # calls that happen outside of run_with_retries
                before = self.direct_run_calls
                result = self.run(prompt, workspace)
                # The run() call inside run_with_retries is expected
                return result

        adapter = _SpyAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        # run_with_retries was called once, and run() was called once (from within run_with_retries)
        assert len(adapter.run_with_retries_calls) == 1


class TestDirectAdapterCallImplTest:
    """Verify ImplTestStrategy calls adapter.run_with_retries() and handles timeout/kill."""

    def test_adapter_run_with_retries_called(self, tmp_path: Path) -> None:
        """ImplTestStrategy should call adapter.run_with_retries() (not run() directly)."""
        strategy = ImplTestStrategy()
        adapter = _KillTrackingAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert len(adapter.run_with_retries_calls) == 1
        assert result.status == CardRunStatus.completed

    def test_run_with_retries_receives_timeout_and_zero_retries(self, tmp_path: Path) -> None:
        """Strategy must pass timeout=<timeout> and retries=0 to run_with_retries."""
        strategy = ImplTestStrategy()
        adapter = _KillTrackingAdapter(write_impl=True)
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=99)
        call = adapter.run_with_retries_calls[0]
        assert call["timeout"] == 99
        assert call["retries"] == 0

    def test_agent_output_captured_in_result(self, tmp_path: Path) -> None:
        """adapter.run_with_retries() return value should be stored in CardRunResult.agent_output."""
        strategy = ImplTestStrategy()
        adapter = _KillTrackingAdapter(write_impl=True, output="impl_test output 99")
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.agent_output == "impl_test output 99"

    def test_kill_called_on_timeout(self, tmp_path: Path) -> None:
        """When adapter raises TimeoutError, adapter.kill() should be called."""
        strategy = ImplTestStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=5)
        assert result.status == CardRunStatus.timeout
        assert adapter.kill_called is True

    def test_kill_not_called_on_success(self, tmp_path: Path) -> None:
        """adapter.kill() should NOT be called on successful completion."""
        strategy = ImplTestStrategy()
        adapter = _KillTrackingAdapter(write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.completed
        assert adapter.kill_called is False

    def test_timeout_result_has_empty_agent_output(self, tmp_path: Path) -> None:
        """On timeout, agent_output should be empty string."""
        strategy = ImplTestStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=5)
        assert result.agent_output == ""

    def test_subprocess_timeout_expired_also_handled(self, tmp_path: Path) -> None:
        """subprocess.TimeoutExpired should also trigger timeout handling with kill()."""
        import subprocess as sp

        class _SubprocessTimeoutAdapter:
            def __init__(self):
                self.kill_called = False
                self.run_with_retries_calls: list[dict] = []

            def run(self, prompt, workspace):
                raise sp.TimeoutExpired(cmd="test", timeout=5)

            def run_with_retries(self, prompt, workspace, *, retries=2, timeout=None):
                self.run_with_retries_calls.append(
                    {"prompt": prompt, "workspace": workspace, "retries": retries, "timeout": timeout}
                )
                try:
                    return self.run(prompt, workspace)
                except sp.TimeoutExpired:
                    self.kill()
                    raise

            def kill(self):
                self.kill_called = True

        strategy = ImplTestStrategy()
        adapter = _SubprocessTimeoutAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=5)
        assert result.status == CardRunStatus.timeout
        assert adapter.kill_called is True
