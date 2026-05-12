"""Pi agent adapter.

Wraps the ``pi`` CLI tool as a concrete :class:`AgentAdapter`.
Passes prompts via stdin and checks subprocess exit status.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from pathlib import Path

from silverquillm.adapters.base import AgentAdapter, register_adapter
from silverquillm.config import BenchmarkConfig


class PiAdapter(AgentAdapter):
    """Adapter that delegates to the ``pi`` CLI.

    Configuration values are read from ``self.config`` (a
    :class:`~silverquillm.config.BenchmarkConfig`).

    The adapter feeds the prompt to ``pi`` via stdin and uses
    non-interactive flags to prevent interactive prompts.
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> None:  # noqa: D401
        """No-op — pi needs no persistent setup."""

    def teardown(self) -> None:  # noqa: D401
        """No-op — pi leaves no persistent resources."""

    def kill(self) -> None:
        """Terminate the running pi subprocess and its process group."""
        proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    proc.kill()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, prompt: str, workspace: Path) -> str:
        """Execute ``pi`` with *prompt* passed via stdin.

        Returns the raw stdout produced by the process.

        Raises
        ------
        subprocess.CalledProcessError
            When the process exits with a non-zero return code.
        """
        cmd = ["pi"]

        process = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self._process = process

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        # Feed prompt via stdin and close
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
register_adapter("pi", PiAdapter)
