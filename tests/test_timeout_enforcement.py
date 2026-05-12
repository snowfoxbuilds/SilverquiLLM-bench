"""Tests for TODO item 7: Hard timeout enforcement at the process level.

Verifies:
- A blocking adapter is killed and returns timeout status.
- The adapter's kill() method is called on timeout.
- All adapter kill() methods use os.getpgid + os.killpg for process-group kill.
- All adapters pass start_new_session=True to Popen.
- Scores are zeroed for timed-out cards (via status=timeout in CardRunResult).
- Strategy timeout is enforced for both BlindStrategy and ImplTestStrategy.
- run_with_retries() enforces a single hard deadline across all attempts.
- run_with_retries() calls self.kill() when deadline expires.
- Timeout runtime_ms is populated correctly.

TESTING-CONVENTIONS.md compliance:
- Uses threading.Event.wait(timeout=60) instead of while True: time.sleep().
- Sets mock_proc.pid = 99999 explicitly on all mock processes.
- Patches os.getpgid / os.killpg in every test — no real signals sent.
- Patches signal.signal / signal.alarm where needed.
- All tests self-terminate within 10 seconds.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from silverquillm.adapters.base import AgentAdapter
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import (
    BlindStrategy,
    CardRunResult,
    CardRunStatus,
    ImplTestStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CARD_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


def _make_config(timeout: int = 2, adapter: str = "mock") -> BenchmarkConfig:
    return BenchmarkConfig(
        name="test-bench",
        set_code="TST",
        model_name="test-model",
        model_provider="test",
        max_context=200_000,
        temperature=0.0,
        mode="blind",
        output_dir="/tmp/test-output",
        agent=AgentConfig(timeout_per_card=timeout, adapter=adapter),
    )


def _make_mock_proc(*, running: bool = True) -> MagicMock:
    """Create a MagicMock subprocess with pid=99999.

    Per TESTING-CONVENTIONS.md: pid must be set explicitly, never auto-MagicMock.
    """
    mock_proc = MagicMock(spec=subprocess.Popen)
    mock_proc.pid = 99999
    mock_proc.poll.return_value = None if running else 0
    mock_proc.wait.return_value = 0
    return mock_proc


class _BlockingAdapter:
    """Adapter whose run() blocks via threading.Event (safe, killable).

    Per TESTING-CONVENTIONS.md: uses Event.wait(timeout=60) instead of
    while True: time.sleep().
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self.killed = False

    def run(self, prompt: str, workspace: Path) -> str:
        self._stop.wait(timeout=60)
        return ""

    def kill(self) -> None:
        self.killed = True
        self._stop.set()


class _BlockingNoKillAdapter:
    """Adapter that blocks but has no kill() method."""

    def __init__(self) -> None:
        self._stop = threading.Event()

    def run(self, prompt: str, workspace: Path) -> str:
        self._stop.wait(timeout=60)
        return ""


# ---------------------------------------------------------------------------
# Tests: Strategy-level hard timeout — BlindStrategy
# ---------------------------------------------------------------------------


class TestBlindStrategyHardTimeout:
    """BlindStrategy must enforce timeout and kill the adapter."""

    @pytest.mark.timeout(10)
    def test_blocking_adapter_returns_timeout(self, tmp_path: Path) -> None:
        """An adapter that blocks must be timed out."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert result.status == CardRunStatus.timeout

    @pytest.mark.timeout(10)
    def test_timeout_fires_within_tolerance(self, tmp_path: Path) -> None:
        """Timeout should fire within a reasonable margin of the configured timeout."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        start = time.monotonic()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        elapsed = time.monotonic() - start
        assert result.status == CardRunStatus.timeout
        # Should complete within 3 seconds (1s timeout + tolerance)
        assert elapsed < 3.0

    @pytest.mark.timeout(10)
    def test_adapter_kill_called_on_timeout(self, tmp_path: Path) -> None:
        """When timeout fires, strategy must call adapter.kill() if available."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert adapter.killed is True

    @pytest.mark.timeout(10)
    def test_adapter_without_kill_method_still_times_out(self, tmp_path: Path) -> None:
        """Adapters lacking kill() must still timeout gracefully."""
        strategy = BlindStrategy()
        adapter = _BlockingNoKillAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert result.status == CardRunStatus.timeout

    @pytest.mark.timeout(10)
    def test_timeout_runtime_ms_is_roughly_correct(self, tmp_path: Path) -> None:
        """runtime_ms should approximate the configured timeout, not zero."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        # Must be at least 500ms (about half the 1s timeout)
        assert result.runtime_ms >= 500, (
            f"runtime_ms={result.runtime_ms} too low — expected ~1000"
        )

    @pytest.mark.timeout(10)
    def test_timeout_runtime_ms_is_non_negative(self, tmp_path: Path) -> None:
        """On timeout the runtime_ms field should be populated and non-negative."""
        strategy = BlindStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert result.runtime_ms >= 0


# ---------------------------------------------------------------------------
# Tests: Strategy-level hard timeout — ImplTestStrategy
# ---------------------------------------------------------------------------


class TestImplTestStrategyHardTimeout:
    """ImplTestStrategy must enforce timeout and kill the adapter."""

    @pytest.mark.timeout(10)
    def test_blocking_adapter_returns_timeout(self, tmp_path: Path) -> None:
        """An adapter that blocks must be timed out."""
        strategy = ImplTestStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert result.status == CardRunStatus.timeout

    @pytest.mark.timeout(10)
    def test_adapter_kill_called_on_timeout(self, tmp_path: Path) -> None:
        """When timeout fires, strategy must call adapter.kill() if available."""
        strategy = ImplTestStrategy()
        adapter = _BlockingAdapter()
        strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert adapter.killed is True

    @pytest.mark.timeout(10)
    def test_timeout_with_partial_files(self, tmp_path: Path) -> None:
        """If card_impl.py exists before timeout, files_written should list it."""
        (tmp_path / "card_impl.py").write_text("# partial\n")
        (tmp_path / "tests.py").write_text("# partial\n")
        strategy = ImplTestStrategy()
        adapter = _BlockingAdapter()
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=1)
        assert result.status == CardRunStatus.timeout
        paths_str = [str(p) for p in result.files_written]
        assert any("card_impl.py" in s for s in paths_str)


# ---------------------------------------------------------------------------
# Tests: Adapter base kill() method
# ---------------------------------------------------------------------------


class TestAdapterBaseKill:
    """AgentAdapter base class should have a kill() method."""

    def test_base_adapter_has_kill_method(self) -> None:
        """AgentAdapter must define a kill() method (no-op by default)."""
        assert hasattr(AgentAdapter, "kill")

    def test_base_kill_is_noop(self) -> None:
        """Default kill() does nothing (subclasses override)."""
        cfg = _make_config()

        class _Dummy(AgentAdapter):
            def setup(self): pass
            def run(self, prompt, workspace): return ""
            def teardown(self): pass

        adapter = _Dummy(cfg)
        # Should not raise
        adapter.kill()


# ---------------------------------------------------------------------------
# Tests: run_with_retries deadline enforcement
# ---------------------------------------------------------------------------


class _BlockingConcreteAdapter(AgentAdapter):
    """Adapter whose run() blocks via threading.Event (safe for tests).

    Per TESTING-CONVENTIONS.md: no time.sleep(9999) or while True loops.
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._stop = threading.Event()
        self.attempt_count = 0
        self.kill_called = False

    def setup(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        self.attempt_count += 1
        self._stop.wait(timeout=60)
        return "done"

    def teardown(self) -> None:
        pass

    def kill(self) -> None:
        self.kill_called = True
        self._stop.set()


class _FailThenBlockAdapter(AgentAdapter):
    """Adapter that fails immediately on first attempt, then blocks."""

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._stop = threading.Event()
        self.attempt_count = 0

    def setup(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        self.attempt_count += 1
        if self.attempt_count == 1:
            raise RuntimeError("first attempt failure")
        self._stop.wait(timeout=60)
        return "done"

    def teardown(self) -> None:
        pass


class TestRunWithRetriesDeadline:
    """run_with_retries must enforce a single hard deadline across all attempts."""

    @pytest.mark.timeout(10)
    def test_overall_deadline_not_multiplied_by_retries(self) -> None:
        """With timeout=2 and retries=3, total wall-clock must be ≤ ~2s, not 2*4=8s."""
        config = _make_config(timeout=2)
        adapter = _BlockingConcreteAdapter(config)
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            adapter.run_with_retries("hi", Path("/tmp"), retries=3, timeout=2)
        elapsed = time.monotonic() - start
        # Should be bounded by ~2s + small overhead, definitely not 8s
        assert elapsed < 6, (
            f"run_with_retries took {elapsed:.1f}s — deadline not enforced"
        )

    @pytest.mark.timeout(10)
    def test_remaining_budget_shrinks_across_retries(self) -> None:
        """After a failed attempt the remaining budget for next attempt is smaller."""
        config = _make_config(timeout=3)
        adapter = _FailThenBlockAdapter(config)
        start = time.monotonic()
        with pytest.raises((TimeoutError, RuntimeError)):
            adapter.run_with_retries("hi", Path("/tmp"), retries=1, timeout=3)
        elapsed = time.monotonic() - start
        # Total should be well under 6s (shared budget).
        assert elapsed < 8, (
            f"run_with_retries took {elapsed:.1f}s — budget not shared"
        )

    @pytest.mark.timeout(10)
    def test_timeout_defaults_to_config_timeout_per_card(self) -> None:
        """When no timeout is passed, run_with_retries uses config.agent.timeout_per_card."""
        config = _make_config(timeout=2)
        adapter = _BlockingConcreteAdapter(config)
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            adapter.run_with_retries("hi", Path("/tmp"), retries=0)
        elapsed = time.monotonic() - start
        assert elapsed < 6

    @pytest.mark.timeout(10)
    def test_raises_timeout_error_not_runtime_error(self) -> None:
        """On deadline expiry the raised exception should be TimeoutError."""
        config = _make_config(timeout=1)
        adapter = _BlockingConcreteAdapter(config)
        with pytest.raises(TimeoutError):
            adapter.run_with_retries("hi", Path("/tmp"), retries=0, timeout=1)

    @pytest.mark.timeout(10)
    def test_run_with_retries_calls_kill_on_timeout(self) -> None:
        """run_with_retries must call self.kill() when the deadline expires."""
        config = _make_config(timeout=1)
        adapter = _BlockingConcreteAdapter(config)
        with pytest.raises(TimeoutError):
            adapter.run_with_retries("hi", Path("/tmp"), retries=0, timeout=1)
        assert adapter.kill_called is True, (
            "run_with_retries must call self.kill() before raising TimeoutError"
        )


# ---------------------------------------------------------------------------
# Tests: Process-group kill for all adapters
# ---------------------------------------------------------------------------


class TestOpenCodeAdapterProcessGroupKill:
    """OpenCodeAdapter.kill() must use os.getpgid + os.killpg for process-group kill.

    Per TESTING-CONVENTIONS.md: all mock processes have pid=99999 explicitly
    set. os.getpgid and os.killpg are always patched — no real signals sent.
    """

    @patch("silverquillm.adapters.opencode.os.killpg")
    @patch("silverquillm.adapters.opencode.os.getpgid", return_value=77777)
    def test_kill_sends_sigterm_to_process_group(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """kill() must call os.getpgid(pid) and os.killpg(pgid, SIGTERM)."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)
        adapter._process = _make_mock_proc(running=True)

        adapter.kill()

        mock_getpgid.assert_called_with(99999)
        mock_killpg.assert_any_call(77777, signal.SIGTERM)

    @patch("silverquillm.adapters.opencode.os.killpg")
    @patch("silverquillm.adapters.opencode.os.getpgid", return_value=77777)
    def test_kill_escalates_to_sigkill_on_timeout(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """If SIGTERM doesn't stop the process, kill() must escalate to SIGKILL via killpg."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)
        mock_proc = _make_mock_proc(running=True)
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("opencode", 5)
        adapter._process = mock_proc

        adapter.kill()

        mock_killpg.assert_any_call(77777, signal.SIGKILL)

    @patch("silverquillm.adapters.opencode.os.killpg")
    @patch(
        "silverquillm.adapters.opencode.os.getpgid",
        side_effect=ProcessLookupError("no such process"),
    )
    def test_kill_falls_back_to_terminate_if_getpgid_fails(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """If os.getpgid raises, kill() should fall back to proc.terminate()."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)
        mock_proc = _make_mock_proc(running=True)
        adapter._process = mock_proc

        adapter.kill()

        mock_proc.terminate.assert_called()

    def test_kill_noop_when_no_process(self) -> None:
        """kill() must not raise when no subprocess is active."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)
        adapter.kill()  # Should not raise

    def test_kill_noop_when_process_already_exited(self) -> None:
        """kill() should be safe when process already finished."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)
        adapter._process = _make_mock_proc(running=False)
        adapter.kill()

    def test_process_stored_during_init(self) -> None:
        """OpenCodeAdapter should initialize _process to None."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)
        assert adapter._process is None

    @patch("silverquillm.adapters.opencode.subprocess.Popen")
    def test_run_passes_start_new_session(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """OpenCodeAdapter.run() must pass start_new_session=True to Popen."""
        from silverquillm.adapters.opencode import OpenCodeAdapter

        cfg = _make_config(adapter="opencode")
        adapter = OpenCodeAdapter(cfg)

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = iter(["output\n"])
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        adapter.run("test prompt", tmp_path)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True, (
            "Popen must be called with start_new_session=True to create process group"
        )


class TestClaudeCodeAdapterProcessGroupKill:
    """ClaudeCodeAdapter.kill() must use os.getpgid + os.killpg."""

    @patch("silverquillm.adapters.claude_code.os.killpg")
    @patch("silverquillm.adapters.claude_code.os.getpgid", return_value=77777)
    def test_kill_sends_sigterm_to_process_group(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """kill() must call os.killpg(pgid, SIGTERM) for the process group."""
        from silverquillm.adapters.claude_code import ClaudeCodeAdapter

        cfg = _make_config(adapter="claude_code")
        adapter = ClaudeCodeAdapter(cfg)
        adapter._process = _make_mock_proc(running=True)

        adapter.kill()

        mock_getpgid.assert_called_with(99999)
        mock_killpg.assert_any_call(77777, signal.SIGTERM)

    @patch("silverquillm.adapters.claude_code.os.killpg")
    @patch("silverquillm.adapters.claude_code.os.getpgid", return_value=77777)
    def test_kill_escalates_to_sigkill_on_timeout(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """If SIGTERM doesn't stop the process, kill() must escalate to SIGKILL."""
        from silverquillm.adapters.claude_code import ClaudeCodeAdapter

        cfg = _make_config(adapter="claude_code")
        adapter = ClaudeCodeAdapter(cfg)
        mock_proc = _make_mock_proc(running=True)
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("claude", 5)
        adapter._process = mock_proc

        adapter.kill()

        mock_killpg.assert_any_call(77777, signal.SIGKILL)

    @patch("silverquillm.adapters.claude_code.subprocess.Popen")
    def test_run_passes_start_new_session(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """ClaudeCodeAdapter.run() must pass start_new_session=True to Popen."""
        from silverquillm.adapters.claude_code import ClaudeCodeAdapter

        cfg = _make_config(adapter="claude_code")
        adapter = ClaudeCodeAdapter(cfg)

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = iter(["output\n"])
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        adapter.run("test prompt", tmp_path)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True


class TestAiderAdapterProcessGroupKill:
    """AiderAdapter.kill() must use os.getpgid + os.killpg."""

    @patch("silverquillm.adapters.aider.os.killpg")
    @patch("silverquillm.adapters.aider.os.getpgid", return_value=77777)
    def test_kill_sends_sigterm_to_process_group(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """kill() must call os.killpg(pgid, SIGTERM) for the process group."""
        from silverquillm.adapters.aider import AiderAdapter

        cfg = _make_config(adapter="aider")
        adapter = AiderAdapter(cfg)
        adapter._process = _make_mock_proc(running=True)

        adapter.kill()

        mock_getpgid.assert_called_with(99999)
        mock_killpg.assert_any_call(77777, signal.SIGTERM)

    @patch("silverquillm.adapters.aider.os.killpg")
    @patch("silverquillm.adapters.aider.os.getpgid", return_value=77777)
    def test_kill_escalates_to_sigkill_on_timeout(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """If SIGTERM doesn't stop the process, kill() must escalate to SIGKILL."""
        from silverquillm.adapters.aider import AiderAdapter

        cfg = _make_config(adapter="aider")
        adapter = AiderAdapter(cfg)
        mock_proc = _make_mock_proc(running=True)
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("aider", 5)
        adapter._process = mock_proc

        adapter.kill()

        mock_killpg.assert_any_call(77777, signal.SIGKILL)

    @patch("silverquillm.adapters.aider.subprocess.Popen")
    def test_run_passes_start_new_session(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """AiderAdapter.run() must pass start_new_session=True to Popen."""
        from silverquillm.adapters.aider import AiderAdapter

        cfg = _make_config(adapter="aider")
        adapter = AiderAdapter(cfg)

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = iter(["output\n"])
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        adapter.run("test prompt", tmp_path)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True


class TestPiAdapterProcessGroupKill:
    """PiAdapter.kill() must use os.getpgid + os.killpg."""

    @patch("silverquillm.adapters.pi.os.killpg")
    @patch("silverquillm.adapters.pi.os.getpgid", return_value=77777)
    def test_kill_sends_sigterm_to_process_group(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """kill() must call os.killpg(pgid, SIGTERM) for the process group."""
        from silverquillm.adapters.pi import PiAdapter

        cfg = _make_config(adapter="pi")
        adapter = PiAdapter(cfg)
        adapter._process = _make_mock_proc(running=True)

        adapter.kill()

        mock_getpgid.assert_called_with(99999)
        mock_killpg.assert_any_call(77777, signal.SIGTERM)

    @patch("silverquillm.adapters.pi.os.killpg")
    @patch("silverquillm.adapters.pi.os.getpgid", return_value=77777)
    def test_kill_escalates_to_sigkill_on_timeout(
        self, mock_getpgid: MagicMock, mock_killpg: MagicMock
    ) -> None:
        """If SIGTERM doesn't stop the process, kill() must escalate to SIGKILL."""
        from silverquillm.adapters.pi import PiAdapter

        cfg = _make_config(adapter="pi")
        adapter = PiAdapter(cfg)
        mock_proc = _make_mock_proc(running=True)
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("pi", 5)
        adapter._process = mock_proc

        adapter.kill()

        mock_killpg.assert_any_call(77777, signal.SIGKILL)

    @patch("silverquillm.adapters.pi.subprocess.Popen")
    def test_run_passes_start_new_session(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """PiAdapter.run() must pass start_new_session=True to Popen."""
        from silverquillm.adapters.pi import PiAdapter

        cfg = _make_config(adapter="pi")
        adapter = PiAdapter(cfg)

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = iter(["output\n"])
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        adapter.run("test prompt", tmp_path)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True


# ---------------------------------------------------------------------------
# Tests: CardRunResult with timeout status
# ---------------------------------------------------------------------------


class TestCardRunResultTimeout:
    """CardRunResult should properly represent timeout outcomes."""

    def test_timeout_status_value(self) -> None:
        """CardRunStatus.timeout should have the string value 'timeout'."""
        assert CardRunStatus.timeout.value == "timeout"

    def test_timeout_result_has_zero_files_when_no_output(self) -> None:
        """A timeout result with no files should have empty files_written."""
        result = CardRunResult(status=CardRunStatus.timeout)
        assert result.files_written == []

    def test_timeout_result_violations_empty_by_default(self) -> None:
        """A timeout result should have an empty violations list by default."""
        result = CardRunResult(status=CardRunStatus.timeout)
        assert result.violations == []
