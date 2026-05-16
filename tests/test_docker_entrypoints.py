"""Static analysis tests for Docker entrypoint files (TODO item 4).

Reads entrypoint.mjs files as text and verifies:
- No engine_work references (stale pattern removed)
- system.log logging with timestamps
- agent_stdout.log output capture
- SIGTERM handler for graceful shutdown
- progress.jsonl writing preserved
- /output directory creation
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

ENTRYPOINT_PATHS = [
    REPO_ROOT / "docker" / "homelab-pi-blind" / "entrypoint.mjs",
    REPO_ROOT / "docker" / "local-pi-blind" / "entrypoint.mjs",
]

ENTRYPOINT_IDS = ["homelab-pi-blind", "local-pi-blind"]


@pytest.fixture(params=zip(ENTRYPOINT_PATHS, ENTRYPOINT_IDS), ids=ENTRYPOINT_IDS)
def entrypoint_text(request) -> str:
    path, _ = request.param
    assert path.is_file(), f"Entrypoint not found: {path}"
    return path.read_text()


# ---------------------------------------------------------------------------
# engine_work removal
# ---------------------------------------------------------------------------

class TestNoEngineWork:
    """engine_work copy pattern must be fully removed."""

    def test_no_engine_work_reference(self, entrypoint_text: str):
        assert "engine_work" not in entrypoint_text, (
            "Entrypoint still references engine_work — stale pattern should be removed"
        )


# ---------------------------------------------------------------------------
# system.log logging
# ---------------------------------------------------------------------------

class TestSystemLog:
    """Entrypoint must write timestamped messages to /output/system.log."""

    def test_system_log_path_present(self, entrypoint_text: str):
        assert "system.log" in entrypoint_text, (
            "Entrypoint must write to system.log"
        )

    def test_timestamp_in_log_function(self, entrypoint_text: str):
        """Log function should produce timestamps (ISO substring or similar)."""
        assert "toISOString" in entrypoint_text, (
            "Log function should use ISO timestamps"
        )

    def test_append_to_system_log(self, entrypoint_text: str):
        """system.log should be written via appendFileSync (not overwritten)."""
        assert "appendFileSync" in entrypoint_text, (
            "system.log should be appended to, not overwritten"
        )


# ---------------------------------------------------------------------------
# agent_stdout.log capture
# ---------------------------------------------------------------------------

class TestAgentStdoutLog:
    """Agent stdout must be teed to /output/agent_stdout.log."""

    def test_agent_stdout_log_present(self, entrypoint_text: str):
        assert "agent_stdout.log" in entrypoint_text, (
            "Entrypoint must capture agent output to agent_stdout.log"
        )


# ---------------------------------------------------------------------------
# SIGTERM handler
# ---------------------------------------------------------------------------

class TestSigtermHandler:
    """Entrypoint must trap SIGTERM for graceful shutdown."""

    def test_sigterm_handler_registered(self, entrypoint_text: str):
        assert "SIGTERM" in entrypoint_text, (
            "Entrypoint must register a SIGTERM handler"
        )

    def test_sigterm_uses_process_on(self, entrypoint_text: str):
        """Node.js entrypoint should use process.on('SIGTERM', ...)."""
        assert 'process.on("SIGTERM"' in entrypoint_text or "process.on('SIGTERM'" in entrypoint_text, (
            "SIGTERM handler should be registered via process.on"
        )


# ---------------------------------------------------------------------------
# progress.jsonl still written
# ---------------------------------------------------------------------------

class TestProgressJsonl:
    """progress.jsonl writing must be preserved."""

    def test_progress_jsonl_present(self, entrypoint_text: str):
        assert "progress.jsonl" in entrypoint_text, (
            "Entrypoint must still write progress.jsonl"
        )


# ---------------------------------------------------------------------------
# /output directory creation
# ---------------------------------------------------------------------------

class TestOutputDirCreation:
    """Entrypoint must create the /output directory."""

    def test_mkdir_output(self, entrypoint_text: str):
        assert 'mkdirSync("/output"' in entrypoint_text or "mkdir -p /output" in entrypoint_text, (
            "Entrypoint must create /output directory"
        )
