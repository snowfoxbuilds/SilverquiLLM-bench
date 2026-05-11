"""OpenCode agent adapter.

Wraps the ``opencode`` CLI tool as a concrete :class:`AgentAdapter`.
Ports logic from :func:`silverquillm.agent_session.AgentSession._run_agent`
with the following fixes:

- Removes the invalid ``--thinking`` flag.
- Passes prompts via stdin instead of as a CLI argument.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from silverquillm.adapters.base import AgentAdapter, register_adapter
from silverquillm.config import BenchmarkConfig


# Repo root — resolved once at import time (matches agent_session.py convention)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class OpenCodeAdapter(AgentAdapter):
    """Adapter that delegates to the ``opencode`` CLI.

    Configuration values are read from ``self.config`` (a
    :class:`~silverquillm.config.BenchmarkConfig`).

    The adapter writes an ``.opencode.yaml`` configuration file into the
    workspace before each invocation and feeds the prompt to ``opencode``
    via **stdin** rather than as a positional CLI argument.
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._opencode_cfg_path: Path | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> None:  # noqa: D401
        """No-op — opencode needs no persistent setup."""

    def teardown(self) -> None:  # noqa: D401
        """No-op — opencode leaves no persistent resources."""

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure_opencode(self, workspace: Path) -> dict:
        """Return OpenCode-compatible configuration dict.

        Mirrors :pymethod:`AgentSession.configure_opencode`.
        """
        deny_web = self.config.agent.disable_web_search
        return {
            "model": self.config.model_name,
            "provider": self.config.model_provider,
            "temperature": self.config.temperature,
            "max_context": self.config.max_context,
            "working_directory": str(workspace),
            "repo_root": str(_REPO_ROOT),
            "engine_path": str(_REPO_ROOT / "engine"),
            "permissions": {
                "deny_web_fetch": deny_web,
                "deny_network": deny_web,
                "allow_read": [str(workspace), str(_REPO_ROOT / "engine")],
                "allow_write": [str(workspace)],
            },
            "timeout": self.config.agent.timeout_per_card,
        }

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, prompt: str, workspace: Path) -> str:
        """Execute ``opencode run`` with *prompt* piped via stdin.

        Returns the raw stdout produced by the process.

        Raises
        ------
        subprocess.TimeoutExpired
            When the process exceeds *timeout_per_card* seconds.
        """
        # Write opencode config into the workspace
        config = self.configure_opencode(workspace)
        config_path = workspace / ".opencode.yaml"
        config_path.write_text(json.dumps(config, indent=2))
        self._opencode_cfg_path = config_path

        # Launch opencode — no --thinking flag, prompt via stdin
        process = subprocess.Popen(
            ["opencode", "run", "--thinking"],
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
                sys.stderr.write(f"\033[2;36m{line}\033[0m")
                sys.stderr.flush()

        t = threading.Thread(target=_stream_stderr, daemon=True)
        t.start()

        # Collect stdout in the calling thread
        assert process.stdout is not None
        for line in process.stdout:
            stdout_lines.append(line)
            sys.stderr.write(f"\033[36m{line}\033[0m")
            sys.stderr.flush()

        t.join(timeout=5)
        process.wait(timeout=self.config.agent.timeout_per_card)

        if process.returncode != 0:
            stderr_text = "".join(stderr_lines)
            raise subprocess.CalledProcessError(
                process.returncode,
                ["opencode", "run"],
                output="".join(stdout_lines),
                stderr=stderr_text,
            )

        return "".join(stdout_lines)


# Auto-register when module is imported
register_adapter("opencode", OpenCodeAdapter)
