"""Aider agent adapter.

Wraps the ``aider`` CLI tool as a concrete :class:`AgentAdapter`.
Passes prompts via a temporary message file using ``--message-file``
and checks subprocess exit status.
"""

from __future__ import annotations

import subprocess
import tempfile
import threading
from pathlib import Path

from silverquillm.adapters.base import AgentAdapter, register_adapter
from silverquillm.config import BenchmarkConfig


class AiderAdapter(AgentAdapter):
    """Adapter that delegates to the ``aider`` CLI.

    Configuration values are read from ``self.config`` (a
    :class:`~silverquillm.config.BenchmarkConfig`).

    The adapter feeds the prompt to ``aider`` via a temporary message file
    using the ``--message-file`` flag.
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> None:  # noqa: D401
        """No-op — aider needs no persistent setup."""

    def teardown(self) -> None:  # noqa: D401
        """No-op — aider leaves no persistent resources."""

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, prompt: str, workspace: Path) -> str:
        """Execute ``aider`` with *prompt* passed via ``--message-file``.

        Returns the raw stdout produced by the process.

        Raises
        ------
        subprocess.CalledProcessError
            When the process exits with a non-zero return code.
        """
        # Write the prompt to a temporary file for --message-file.
        # Placed outside the workspace so aider doesn't see it in the working tree.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            prefix="aider_prompt_",
            delete=False,
        ) as f:
            f.write(prompt)
            message_file = f.name

        try:
            cmd = [
                "aider",
                "--no-auto-commits",
                "--yes-always",
                "--model", self.config.model_name,
                "--message-file", message_file,
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

            # Close stdin immediately — prompt is via file
            assert process.stdin is not None
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
        finally:
            # Clean up the temporary message file
            Path(message_file).unlink(missing_ok=True)


# Auto-register when module is imported
register_adapter("aider", AiderAdapter)
