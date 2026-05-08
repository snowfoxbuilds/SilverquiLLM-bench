"""Tests for TODO item 8: PiAdapter implementation.

Verifies:
- PiAdapter is a concrete subclass of AgentAdapter.
- It registers as "pi" in the adapter factory.
- get_adapter returns PiAdapter when adapter=="pi".
- Prompt is passed via stdin (piped to the subprocess).
- Command is just ``pi`` with no unverified CLI flags.
- Non-zero exit raises subprocess.CalledProcessError with stderr.
- setup() and teardown() complete without error.
- Edge cases: empty output, subprocess failure, workspace as cwd.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.adapters import AgentAdapter, get_adapter
from silverquillm.adapters.pi import PiAdapter
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**agent_overrides) -> BenchmarkConfig:
    """Create a minimal BenchmarkConfig with pi adapter."""
    agent_kwargs = {
        "adapter": "pi",
        "timeout_per_card": 300,
        "disable_web_search": True,
    }
    agent_kwargs.update(agent_overrides)
    return BenchmarkConfig(
        name="test",
        set_code="SOS",
        model_name="test-model",
        model_provider="test-provider",
        agent=AgentConfig(**agent_kwargs),
    )


def _mock_popen(stdout_text: str = "agent output\n", returncode: int = 0):
    """Return a mock Popen instance that yields stdout_text line by line."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = iter(stdout_text.splitlines(keepends=True))
    mock_proc.stderr = iter([])
    mock_proc.wait.return_value = returncode
    mock_proc.returncode = returncode
    return mock_proc


# ---------------------------------------------------------------------------
# Subclass / type checks
# ---------------------------------------------------------------------------

class TestPiAdapterType:
    """Verify PiAdapter is a proper AgentAdapter subclass."""

    def test_is_subclass_of_agent_adapter(self) -> None:
        """PiAdapter must inherit from AgentAdapter."""
        assert issubclass(PiAdapter, AgentAdapter)

    def test_is_concrete(self) -> None:
        """PiAdapter must be instantiable (not abstract)."""
        config = _make_config()
        adapter = PiAdapter(config)
        assert isinstance(adapter, AgentAdapter)


# ---------------------------------------------------------------------------
# Factory / registry
# ---------------------------------------------------------------------------

class TestAdapterFactory:
    """Verify PiAdapter is wired into the adapter factory."""

    def test_get_adapter_returns_pi(self) -> None:
        """get_adapter should return a PiAdapter when adapter=='pi'."""
        config = _make_config()
        adapter = get_adapter(config)
        assert isinstance(adapter, PiAdapter)

    def test_get_adapter_stores_config(self) -> None:
        """The returned adapter must hold a reference to the config."""
        config = _make_config()
        adapter = get_adapter(config)
        assert adapter.config is config


# ---------------------------------------------------------------------------
# setup / teardown
# ---------------------------------------------------------------------------

class TestLifecycle:
    """Verify setup() and teardown() work without error."""

    def test_setup_completes(self) -> None:
        adapter = PiAdapter(_make_config())
        adapter.setup()  # should not raise

    def test_teardown_completes(self) -> None:
        adapter = PiAdapter(_make_config())
        adapter.teardown()  # should not raise


# ---------------------------------------------------------------------------
# Prompt via stdin
# ---------------------------------------------------------------------------

class TestPromptViaStdin:
    """Verify prompts are piped via stdin, not as a CLI argument."""

    def test_prompt_written_to_stdin(self, tmp_path: Path) -> None:
        """The prompt text must be written to the process's stdin."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            adapter.run("hello world", tmp_path)

        mock_proc.stdin.write.assert_called_with("hello world")

    def test_prompt_not_in_cli_args(self, tmp_path: Path) -> None:
        """The prompt text must NOT appear as a positional CLI argument."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("my prompt text", tmp_path)

        args = popen_mock.call_args[0][0]
        assert "my prompt text" not in args, "Prompt must not be passed as CLI arg"

    def test_stdin_closed_after_write(self, tmp_path: Path) -> None:
        """stdin must be closed after writing the prompt so the process receives EOF."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            adapter.run("prompt", tmp_path)

        mock_proc.stdin.close.assert_called_once()


# ---------------------------------------------------------------------------
# Command construction (conservative — no unverified flags)
# ---------------------------------------------------------------------------

class TestCommandConstruction:
    """Verify the command invokes ``pi`` without unverified CLI flags."""

    def test_command_starts_with_pi(self, tmp_path: Path) -> None:
        """The CLI command must start with 'pi'."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        args = popen_mock.call_args[0][0]
        assert args[0] == "pi", "Command must start with 'pi'"

    def test_no_unverified_flags(self, tmp_path: Path) -> None:
        """The command must NOT include --no-interactive or --model flags."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        args = popen_mock.call_args[0][0]
        assert "--no-interactive" not in args, "--no-interactive is not a verified pi CLI flag"
        assert "--model" not in args, "--model is not a verified pi CLI flag"


# ---------------------------------------------------------------------------
# Return value / stdout capture
# ---------------------------------------------------------------------------

class TestRunOutput:
    """Verify run() returns captured stdout."""

    def test_returns_stdout(self, tmp_path: Path) -> None:
        """run() must return the process stdout as a string."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen(stdout_text="line1\nline2\n")

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("prompt", tmp_path)

        assert result == "line1\nline2\n"


# ---------------------------------------------------------------------------
# Exit status / error handling
# ---------------------------------------------------------------------------

class TestExitStatus:
    """Verify non-zero exit raises CalledProcessError."""

    def test_nonzero_exit_raises(self, tmp_path: Path) -> None:
        """Non-zero exit code must raise subprocess.CalledProcessError."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen(stdout_text="partial output\n", returncode=1)

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                adapter.run("prompt", tmp_path)

        assert exc_info.value.returncode == 1

    def test_nonzero_exit_includes_stderr(self, tmp_path: Path) -> None:
        """CalledProcessError must include captured stderr."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen(returncode=1)
        mock_proc.stderr = iter(["error: something broke\n"])

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                adapter.run("prompt", tmp_path)

        assert "something broke" in exc_info.value.stderr


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty prompt, empty output, workspace cwd, stdin pipe."""

    def test_empty_prompt(self, tmp_path: Path) -> None:
        """An empty prompt string should still be written to stdin without error."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen(stdout_text="")

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("", tmp_path)

        mock_proc.stdin.write.assert_called_with("")
        assert result == ""

    def test_empty_output(self, tmp_path: Path) -> None:
        """When the process produces no stdout, run() should return empty string."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen(stdout_text="")

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("some prompt", tmp_path)

        assert result == ""

    def test_popen_uses_workspace_as_cwd(self, tmp_path: Path) -> None:
        """Popen must set cwd to the workspace directory."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        kwargs = popen_mock.call_args[1]  # keyword args
        assert kwargs["cwd"] == str(tmp_path)

    def test_stdin_pipe_requested(self, tmp_path: Path) -> None:
        """Popen must be called with stdin=PIPE to allow writing the prompt."""
        config = _make_config()
        adapter = PiAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.pi.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        kwargs = popen_mock.call_args[1]
        assert kwargs["stdin"] == subprocess.PIPE
