"""Claude Code agent adapter.

Wraps the ``claude`` CLI tool as a concrete :class:`AgentAdapter`.
Passes prompts via stdin and checks subprocess exit status.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from silverquillm.adapters.base import AgentAdapter, register_adapter
from silverquillm.config import BenchmarkConfig


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter that delegates to the ``claude`` CLI.

    Configuration values are read from ``self.config`` (a
    :class:`~silverquillm.config.BenchmarkConfig`).

    The adapter feeds the prompt to ``claude`` via **stdin**.
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> None:  # noqa: D401
        """No-op — claude needs no persistent setup."""

    def teardown(self) -> None:  # noqa: D401
        """No-op — claude leaves no persistent resources."""

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, prompt: str, workspace: Path) -> str:
        """Execute ``claude`` with *prompt* piped via stdin.

        Returns the raw stdout produced by the process.

        Raises
        ------
        subprocess.CalledProcessError
            When the process exits with a non-zero return code.
        """
        cmd = [
            "claude",
            "--print",
            "--model", self.config.model_name,
        ]

        process = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        # Feed the prompt via stdin then close it
        assert process.stdin is not None
        process.stdin.write(prompt)
        process.stdin.close()

        # Stream stderr in a background thread
        def _stream_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                stderr_lines.append(line)

        t = threading.Thread(target=_stream_stderr, daemon=True)
        t.start()

        # Collect stdout in the calling thread
        assert process.stdout is not None
        for line in process.stdout:
            stdout_lines.append(line)

        t.join(timeout=5)
        process.wait(timeout=self.config.agent.timeout_per_card)

        if process.returncode != 0:
            stderr_text = "".join(stderr_lines)
            raise subprocess.CalledProcessError(
                process.returncode,
                cmd,
                output="".join(stdout_lines),
                stderr=stderr_text,
            )

        return "".join(stdout_lines)


# Auto-register when module is imported
register_adapter("claude_code", ClaudeCodeAdapter)
