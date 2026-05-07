"""Tests for TODO item 4: AgentAdapter ABC, retry/timeout logic, and factory.

Tests verify:
- AgentAdapter is an ABC and cannot be instantiated directly.
- Concrete subclasses must implement run, setup, teardown.
- run_with_retries handles retry logic and raises after max attempts.
- run_with_retries applies timeout via _run_with_timeout.
- get_adapter() returns the correct adapter for registered names.
- get_adapter() raises ValueError for unknown adapter names.
- register_adapter() makes adapters available to get_adapter().
- Edge cases: empty prompt, zero retries, exponential back-off.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.adapters.base import (
    AgentAdapter,
    _ADAPTER_REGISTRY,
    get_adapter,
    register_adapter,
)
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(adapter: str = "dummy", timeout: int = 60) -> BenchmarkConfig:
    return BenchmarkConfig(
        name="test",
        set_code="SOS",
        model_name="m",
        model_provider="p",
        agent=AgentConfig(adapter=adapter, timeout_per_card=timeout),
    )


class DummyAdapter(AgentAdapter):
    """Minimal concrete adapter for testing."""

    def setup(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        return f"echo:{prompt}"

    def teardown(self) -> None:
        pass


class FailNTimesAdapter(AgentAdapter):
    """Adapter that fails N times then succeeds."""

    def __init__(self, config: BenchmarkConfig, fail_count: int = 2) -> None:
        super().__init__(config)
        self.fail_count = fail_count
        self.attempts = 0

    def setup(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise RuntimeError(f"Failure #{self.attempts}")
        return "ok"

    def teardown(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the adapter registry around each test."""
    saved = dict(_ADAPTER_REGISTRY)
    yield
    _ADAPTER_REGISTRY.clear()
    _ADAPTER_REGISTRY.update(saved)


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------

class TestABCEnforcement:
    def test_cannot_instantiate_directly(self):
        """AgentAdapter is abstract; instantiation must raise TypeError."""
        with pytest.raises(TypeError):
            AgentAdapter(_make_config())  # type: ignore[abstract]

    def test_missing_run_raises(self):
        """Subclass missing 'run' cannot be instantiated."""

        class Incomplete(AgentAdapter):
            def setup(self) -> None: ...
            def teardown(self) -> None: ...

        with pytest.raises(TypeError):
            Incomplete(_make_config())

    def test_missing_setup_raises(self):
        """Subclass missing 'setup' cannot be instantiated."""

        class Incomplete(AgentAdapter):
            def run(self, prompt: str, workspace: Path) -> str:
                return ""
            def teardown(self) -> None: ...

        with pytest.raises(TypeError):
            Incomplete(_make_config())

    def test_missing_teardown_raises(self):
        """Subclass missing 'teardown' cannot be instantiated."""

        class Incomplete(AgentAdapter):
            def run(self, prompt: str, workspace: Path) -> str:
                return ""
            def setup(self) -> None: ...

        with pytest.raises(TypeError):
            Incomplete(_make_config())

    def test_concrete_subclass_instantiates(self):
        """Fully implemented subclass can be instantiated."""
        adapter = DummyAdapter(_make_config())
        assert isinstance(adapter, AgentAdapter)


# ---------------------------------------------------------------------------
# run / setup / teardown interface
# ---------------------------------------------------------------------------

class TestConcreteAdapter:
    def test_run_returns_string(self):
        adapter = DummyAdapter(_make_config())
        result = adapter.run("hello", Path("/tmp"))
        assert result == "echo:hello"

    def test_run_with_empty_prompt(self):
        adapter = DummyAdapter(_make_config())
        result = adapter.run("", Path("/tmp"))
        assert result == "echo:"

    def test_config_stored(self):
        cfg = _make_config()
        adapter = DummyAdapter(cfg)
        assert adapter.config is cfg


# ---------------------------------------------------------------------------
# run_with_retries
# ---------------------------------------------------------------------------

class TestRunWithRetries:
    def test_success_on_first_attempt(self):
        adapter = DummyAdapter(_make_config())
        result = adapter.run_with_retries("hi", Path("/tmp"), retries=2, timeout=60)
        assert result == "echo:hi"

    def test_retries_until_success(self):
        """Adapter fails once then succeeds; run_with_retries should return ok."""
        adapter = FailNTimesAdapter(_make_config(), fail_count=1)
        with patch("silverquillm.adapters.base.time.sleep"):
            result = adapter.run_with_retries("x", Path("/tmp"), retries=2, timeout=60)
        assert result == "ok"
        assert adapter.attempts == 2

    def test_raises_after_all_retries_exhausted(self):
        """When every attempt fails, RuntimeError is raised."""
        adapter = FailNTimesAdapter(_make_config(), fail_count=10)
        with patch("silverquillm.adapters.base.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after 3 attempts"):
                adapter.run_with_retries("x", Path("/tmp"), retries=2, timeout=60)
        assert adapter.attempts == 3  # 1 initial + 2 retries

    def test_zero_retries_means_single_attempt(self):
        adapter = FailNTimesAdapter(_make_config(), fail_count=1)
        with patch("silverquillm.adapters.base.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after 1 attempts"):
                adapter.run_with_retries("x", Path("/tmp"), retries=0, timeout=60)
        assert adapter.attempts == 1

    def test_timeout_defaults_to_config_value(self):
        """When timeout is not passed, config.agent.timeout_per_card is used."""
        cfg = _make_config(timeout=42)
        adapter = DummyAdapter(cfg)
        with patch.object(adapter, "_run_with_timeout", return_value="ok") as m:
            adapter.run_with_retries("p", Path("/tmp"), retries=0)
        m.assert_called_once_with("p", Path("/tmp"), 42)

    def test_explicit_timeout_overrides_config(self):
        cfg = _make_config(timeout=42)
        adapter = DummyAdapter(cfg)
        with patch.object(adapter, "_run_with_timeout", return_value="ok") as m:
            adapter.run_with_retries("p", Path("/tmp"), retries=0, timeout=99)
        m.assert_called_once_with("p", Path("/tmp"), 99)

    def test_exponential_backoff_sleep(self):
        """Back-off sleeps should follow 2**attempt pattern."""
        adapter = FailNTimesAdapter(_make_config(), fail_count=10)
        with patch("silverquillm.adapters.base.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError):
                adapter.run_with_retries("x", Path("/tmp"), retries=3, timeout=60)
        # Sleeps between attempts: 2^0=1, 2^1=2, 2^2=4
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_args == [1, 2, 4]

    def test_timeout_error_is_retried(self):
        """TimeoutError from _run_with_timeout should be retried."""
        cfg = _make_config()
        adapter = DummyAdapter(cfg)
        call_count = 0

        def _fake_run_with_timeout(prompt, workspace, timeout):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timed out")
            return "ok"

        with patch.object(adapter, "_run_with_timeout", side_effect=_fake_run_with_timeout):
            with patch("silverquillm.adapters.base.time.sleep"):
                result = adapter.run_with_retries("p", Path("/tmp"), retries=2, timeout=10)
        assert result == "ok"


# ---------------------------------------------------------------------------
# Registry & factory
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_register_and_get_adapter(self):
        register_adapter("dummy", DummyAdapter)
        cfg = _make_config(adapter="dummy")
        adapter = get_adapter(cfg)
        assert isinstance(adapter, DummyAdapter)
        assert adapter.config is cfg

    def test_get_adapter_unknown_raises_valueerror(self):
        cfg = _make_config(adapter="nonexistent")
        with pytest.raises(ValueError, match="Unknown adapter.*nonexistent"):
            get_adapter(cfg)

    def test_register_overwrites_previous(self):
        """Registering the same name twice replaces the earlier entry."""

        class OtherAdapter(DummyAdapter):
            pass

        register_adapter("dup", DummyAdapter)
        register_adapter("dup", OtherAdapter)
        cfg = _make_config(adapter="dup")
        assert isinstance(get_adapter(cfg), OtherAdapter)

    def test_valueerror_lists_available(self):
        """ValueError message should list available adapters."""
        register_adapter("alpha", DummyAdapter)
        register_adapter("beta", DummyAdapter)
        cfg = _make_config(adapter="missing")
        with pytest.raises(ValueError, match="alpha.*beta"):
            get_adapter(cfg)
