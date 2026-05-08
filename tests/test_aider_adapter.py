"""Tests for TODO item 7: AiderAdapter implementation.

Verifies:
- AiderAdapter is a concrete subclass of AgentAdapter.
- It registers as "aider" in the adapter factory.
- get_adapter returns AiderAdapter when adapter=="aider".
- Prompt is passed via --message-file (temporary file), not stdin or CLI arg.
- Non-zero exit raises subprocess.CalledProcessError with stderr.
- setup() and teardown() complete without error.
- Edge cases: empty prompt, subprocess failure, message file cleanup.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.adapters import AgentAdapter, get_adapter
from silverquillm.adapters.aider import AiderAdapter
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**agent_overrides) -> BenchmarkConfig:
    """Create a minimal BenchmarkConfig with aider adapter."""
    agent_kwargs = {
        "adapter": "aider",
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

class TestAiderAdapterType:
    """Verify AiderAdapter is a proper AgentAdapter subclass."""

    def test_is_subclass_of_agent_adapter(self) -> None:
        """AiderAdapter must inherit from AgentAdapter."""
        assert issubclass(AiderAdapter, AgentAdapter)

    def test_is_concrete(self) -> None:
        """AiderAdapter must be instantiable (not abstract)."""
        config = _make_config()
        adapter = AiderAdapter(config)
        assert isinstance(adapter, AgentAdapter)


# ---------------------------------------------------------------------------
# Factory / registry
# ---------------------------------------------------------------------------

class TestAdapterFactory:
    """Verify AiderAdapter is wired into the adapter factory."""

    def test_get_adapter_returns_aider(self) -> None:
        """get_adapter should return an AiderAdapter when adapter=='aider'."""
        config = _make_config()
        adapter = get_adapter(config)
        assert isinstance(adapter, AiderAdapter)

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
        adapter = AiderAdapter(_make_config())
        adapter.setup()  # should not raise

    def test_teardown_completes(self) -> None:
        adapter = AiderAdapter(_make_config())
        adapter.teardown()  # should not raise


# ---------------------------------------------------------------------------
# Prompt delivery via --message-file
# ---------------------------------------------------------------------------

class TestPromptViaMessageFile:
    """Verify prompts are passed via --message-file, not stdin or CLI arg."""

    def test_message_file_flag_in_cli_args(self, tmp_path: Path) -> None:
        """The Popen call must include '--message-file' in its argv."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("test prompt", tmp_path)

        args = popen_mock.call_args[0][0]
        assert "--message-file" in args, "--message-file flag must appear in CLI command"

    def test_prompt_not_in_cli_args(self, tmp_path: Path) -> None:
        """The prompt text must NOT appear as a positional CLI argument."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("my unique prompt text", tmp_path)

        args = popen_mock.call_args[0][0]
        assert "my unique prompt text" not in args, "Prompt must not be passed as CLI arg"

    def test_stdin_closed_immediately(self, tmp_path: Path) -> None:
        """stdin must be closed since prompt is delivered via file, not stdin."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc):
            adapter.run("prompt", tmp_path)

        mock_proc.stdin.close.assert_called_once()

    def test_message_file_contains_prompt(self, tmp_path: Path) -> None:
        """The temporary message file written must contain the prompt text."""
        config = _make_config()
        adapter = AiderAdapter(config)

        written_content = None

        original_popen = subprocess.Popen

        def capture_popen(cmd, **kwargs):
            nonlocal written_content
            # Find the message file path from the command
            idx = cmd.index("--message-file")
            msg_file = cmd[idx + 1]
            written_content = Path(msg_file).read_text()
            return _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", side_effect=capture_popen):
            adapter.run("hello aider", tmp_path)

        assert written_content == "hello aider"


# ---------------------------------------------------------------------------
# CLI command construction
# ---------------------------------------------------------------------------

class TestCLIConstruction:
    """Verify the CLI command is built correctly."""

    def test_aider_is_first_arg(self, tmp_path: Path) -> None:
        """The command must start with 'aider'."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        args = popen_mock.call_args[0][0]
        assert args[0] == "aider"

    def test_model_passed_to_cli(self, tmp_path: Path) -> None:
        """The --model flag must include the configured model name."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        args = popen_mock.call_args[0][0]
        idx = args.index("--model")
        assert args[idx + 1] == "test-model"

    def test_no_auto_commits_flag(self, tmp_path: Path) -> None:
        """The --no-auto-commits flag must be present."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        args = popen_mock.call_args[0][0]
        assert "--no-auto-commits" in args

    def test_workspace_used_as_cwd(self, tmp_path: Path) -> None:
        """Popen must set cwd to the workspace directory."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        kwargs = popen_mock.call_args[1]
        assert kwargs["cwd"] == str(tmp_path)

    def test_stdin_pipe_requested(self, tmp_path: Path) -> None:
        """Popen must be called with stdin=PIPE."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc) as popen_mock:
            adapter.run("prompt", tmp_path)

        kwargs = popen_mock.call_args[1]
        assert kwargs["stdin"] == subprocess.PIPE


# ---------------------------------------------------------------------------
# Return value / stdout capture
# ---------------------------------------------------------------------------

class TestRunOutput:
    """Verify run() returns captured stdout."""

    def test_returns_stdout(self, tmp_path: Path) -> None:
        """run() must return the process stdout as a string."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen(stdout_text="line1\nline2\n")

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("prompt", tmp_path)

        assert result == "line1\nline2\n"


# ---------------------------------------------------------------------------
# Exit status checking
# ---------------------------------------------------------------------------

class TestExitStatus:
    """Verify non-zero exit raises CalledProcessError."""

    def test_nonzero_exit_raises(self, tmp_path: Path) -> None:
        """A non-zero return code must raise subprocess.CalledProcessError."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen(stdout_text="partial output\n", returncode=1)

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                adapter.run("prompt", tmp_path)

        assert exc_info.value.returncode == 1

    def test_nonzero_exit_includes_stderr(self, tmp_path: Path) -> None:
        """CalledProcessError must include captured stderr."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = iter(["output\n"])
        mock_proc.stderr = iter(["error message\n"])
        mock_proc.wait.return_value = 2
        mock_proc.returncode = 2

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                adapter.run("prompt", tmp_path)

        assert "error message" in exc_info.value.stderr

    def test_zero_exit_no_exception(self, tmp_path: Path) -> None:
        """A zero return code must NOT raise."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen(returncode=0)

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("prompt", tmp_path)

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty prompt, empty output, message file cleanup."""

    def test_empty_prompt(self, tmp_path: Path) -> None:
        """An empty prompt string should still work without error."""
        config = _make_config()
        adapter = AiderAdapter(config)
        mock_proc = _mock_popen(stdout_text="")

        with patch("silverquillm.adapters.aider.subprocess.Popen", return_value=mock_proc):
            result = adapter.run("", tmp_path)

        assert result == ""

    def test_message_file_cleaned_up_on_success(self, tmp_path: Path) -> None:
        """The temporary message file must be deleted after run() completes."""
        config = _make_config()
        adapter = AiderAdapter(config)

        created_files: list[str] = []

        def capture_popen(cmd, **kwargs):
            idx = cmd.index("--message-file")
            created_files.append(cmd[idx + 1])
            return _mock_popen()

        with patch("silverquillm.adapters.aider.subprocess.Popen", side_effect=capture_popen):
            adapter.run("prompt", tmp_path)

        assert len(created_files) == 1
        assert not Path(created_files[0]).exists(), "Message file must be cleaned up after run"

    def test_message_file_cleaned_up_on_failure(self, tmp_path: Path) -> None:
        """The temporary message file must be deleted even if the process fails."""
        config = _make_config()
        adapter = AiderAdapter(config)

        created_files: list[str] = []

        def capture_popen(cmd, **kwargs):
            idx = cmd.index("--message-file")
            created_files.append(cmd[idx + 1])
            return _mock_popen(returncode=1)

        with patch("silverquillm.adapters.aider.subprocess.Popen", side_effect=capture_popen):
            with pytest.raises(subprocess.CalledProcessError):
                adapter.run("prompt", tmp_path)

        assert len(created_files) == 1
        assert not Path(created_files[0]).exists(), "Message file must be cleaned up even on failure"
