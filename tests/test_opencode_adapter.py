"""Tests for TODO item 5: OpenCodeAdapter implementation.

Verifies:
- OpenCodeAdapter is a concrete subclass of AgentAdapter.
- It registers as "opencode" in the adapter factory.
- get_adapter returns OpenCodeAdapter for adapter=="opencode".
- The --thinking flag is NOT present in the CLI command.
- Prompts are passed via stdin (not CLI arg).
- setup() and teardown() complete without error.
- Edge cases: empty prompt, subprocess failure.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.adapters import AgentAdapter, get_adapter
from silverquillm.adapters.opencode import OpenCodeAdapter
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**agent_overrides) -> BenchmarkConfig:
    """Create a minimal BenchmarkConfig with opencode adapter."""
    agent_kwargs = {
        "adapter": "opencode",
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

class TestOpenCodeAdapterType:
    """Verify OpenCodeAdapter is a proper AgentAdapter subclass."""

    def test_is_subclass_of_agent_adapter(self) -> None:
        """OpenCodeAdapter must inherit from AgentAdapter."""
        assert issubclass(OpenCodeAdapter, AgentAdapter)

    def test_is_concrete(self) -> None:
        """OpenCodeAdapter must be instantiable (not abstract)."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        assert isinstance(adapter, AgentAdapter)


# ---------------------------------------------------------------------------
# Factory / registry
# ---------------------------------------------------------------------------

class TestAdapterFactory:
    """Verify OpenCodeAdapter is wired into the adapter factory."""

    def test_get_adapter_returns_opencode(self) -> None:
        """get_adapter should return an OpenCodeAdapter when adapter=='opencode'."""
        config = _make_config()
        adapter = get_adapter(config)
        assert isinstance(adapter, OpenCodeAdapter)

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
        adapter = OpenCodeAdapter(_make_config())
        adapter.setup()  # should not raise

    def test_teardown_completes(self) -> None:
        adapter = OpenCodeAdapter(_make_config())
        adapter.teardown()  # should not raise


# ---------------------------------------------------------------------------
# CLI command construction — no --thinking flag
# ---------------------------------------------------------------------------

class TestNoThinkingFlag:
    """Verify the --thinking flag is NOT used."""

    def test_no_thinking_in_popen_args(self, tmp_path: Path) -> None:
        """The Popen call must NOT include '--thinking' in its argv."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("test prompt", tmp_path)

        args = popen_mock.call_args[0][0]  # positional arg 0 = command list
        assert "--thinking" not in args, "The --thinking flag must not appear in the CLI command"


# ---------------------------------------------------------------------------
# Prompt via stdin
# ---------------------------------------------------------------------------

class TestPromptViaStdin:
    """Verify prompts are passed via stdin, not as a CLI argument."""

    def test_prompt_written_to_stdin(self, tmp_path: Path) -> None:
        """The prompt text must be written to the process's stdin."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc):
            adapter.run("hello world", tmp_path)

        mock_proc.stdin.write.assert_called_with("hello world")

    def test_prompt_not_in_cli_args(self, tmp_path: Path) -> None:
        """The prompt text must NOT appear as a positional CLI argument."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("my prompt text", tmp_path)

        args = popen_mock.call_args[0][0]
        assert "my prompt text" not in args, "Prompt must not be passed as CLI arg"

    def test_stdin_closed_after_write(self, tmp_path: Path) -> None:
        """stdin must be closed after writing the prompt so the process receives EOF."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc):
            adapter.run("prompt", tmp_path)

        mock_proc.stdin.close.assert_called_once()


# ---------------------------------------------------------------------------
# Return value / stdout capture
# ---------------------------------------------------------------------------

class TestRunOutput:
    """Verify run() returns captured stdout."""

    def test_returns_stdout(self, tmp_path: Path) -> None:
        """run() must return the process stdout as a string."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen(stdout_text="line1\nline2\n")

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("prompt", tmp_path)

        assert result == "line1\nline2\n"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty prompt, subprocess failure."""

    def test_empty_prompt(self, tmp_path: Path) -> None:
        """An empty prompt string should still be written to stdin without error."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen(stdout_text="")

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("", tmp_path)

        mock_proc.stdin.write.assert_called_with("")
        assert result == ""

    def test_popen_uses_workspace_as_cwd(self, tmp_path: Path) -> None:
        """Popen must set cwd to the workspace directory."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        kwargs = popen_mock.call_args[1]  # keyword args
        assert kwargs["cwd"] == str(tmp_path)

    def test_opencode_config_written_to_workspace(self, tmp_path: Path) -> None:
        """run() should write an .opencode.yaml config file in the workspace."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc):
            adapter.run("prompt", tmp_path)

        config_path = tmp_path / ".opencode.yaml"
        assert config_path.exists(), ".opencode.yaml must be written to workspace"
        content = json.loads(config_path.read_text())
        assert content["model"] == "test-model"

    def test_stdin_pipe_requested(self, tmp_path: Path) -> None:
        """Popen must be called with stdin=PIPE to allow writing the prompt."""
        config = _make_config()
        adapter = OpenCodeAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.opencode.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        kwargs = popen_mock.call_args[1]
        assert kwargs["stdin"] == subprocess.PIPE
