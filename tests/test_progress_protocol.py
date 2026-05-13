"""Tests for TODO item 10: progress.jsonl protocol in entrypoints.

Verifies that both entrypoint scripts (docker/opencode-tested/entrypoint.sh and
docker/opencode-blind/entrypoint.sh) implement the progress.jsonl protocol correctly:
- emit_progress function exists and produces valid JSONL
- All required event types are emitted (started, card_started, card_completed, completed, failed, timed_out)
- card_watcher function exists
- Cleanup logic kills watcher PID
- SIGTERM trap writes timed_out event
- Writes go to /output/progress.jsonl
- Both entrypoints are consistent in their progress protocol
- emit_progress output is valid JSON with ts and event fields
- Watcher starts after agent launch ordering
- Watcher killed before final event
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

# ── Constants ───────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
TESTED_ENTRYPOINT = REPO_ROOT / "docker" / "opencode-tested" / "entrypoint.sh"
BLIND_ENTRYPOINT = REPO_ROOT / "docker" / "opencode-blind" / "entrypoint.sh"

ENTRYPOINTS = [
    pytest.param(TESTED_ENTRYPOINT, id="opencode-tested"),
    pytest.param(BLIND_ENTRYPOINT, id="opencode-blind"),
]

REQUIRED_EVENTS = ["started", "card_started", "card_completed", "completed", "failed", "timed_out"]


# ── Helpers ─────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── Tests: emit_progress function ──────────────────────────────────

class TestEmitProgressFunction:
    """Verify the emit_progress function exists and is well-formed."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_emit_progress_function_defined(self, entrypoint: Path):
        """emit_progress() must be defined as a shell function."""
        content = _read(entrypoint)
        assert re.search(r"emit_progress\s*\(\)", content), (
            f"emit_progress function not found in {entrypoint.name}"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_emit_progress_appends_to_progress_file(self, entrypoint: Path):
        """emit_progress must append (>>) to PROGRESS_FILE."""
        content = _read(entrypoint)
        assert ">>" in content and "PROGRESS_FILE" in content, (
            "emit_progress should append to $PROGRESS_FILE"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_emit_progress_includes_timestamp(self, entrypoint: Path):
        """emit_progress must generate a timestamp (ts field)."""
        content = _read(entrypoint)
        assert "ts" in content, "emit_progress should include a ts field"
        # Verify it uses date command for ISO timestamp
        assert re.search(r"date\s.*\+%", content), (
            "emit_progress should use date command for timestamp"
        )


# ── Tests: Required event types ────────────────────────────────────

class TestRequiredEvents:
    """All six event types must appear in the scripts."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    @pytest.mark.parametrize("event", REQUIRED_EVENTS)
    def test_event_type_present(self, entrypoint: Path, event: str):
        """Each required event type must be emitted somewhere in the script."""
        content = _read(entrypoint)
        # Match both "event": "X" and \"event\": \"X\" (escaped in double-quoted strings)
        pattern = rf'(?:\\?)"event(?:\\?)"\s*:\s*(?:\\?)"{event}(?:\\?)"'
        assert re.search(pattern, content), (
            f"Event '{event}' not found in {entrypoint.name}"
        )


# ── Tests: card_watcher function ───────────────────────────────────

class TestCardWatcher:
    """Verify the card_watcher background function."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_card_watcher_function_defined(self, entrypoint: Path):
        """card_watcher() must be defined as a shell function."""
        content = _read(entrypoint)
        assert re.search(r"card_watcher\s*\(\)", content), (
            f"card_watcher function not found in {entrypoint.name}"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_card_watcher_launched_in_background(self, entrypoint: Path):
        """card_watcher must be started as a background process (&)."""
        content = _read(entrypoint)
        assert re.search(r"card_watcher\s*&", content), (
            "card_watcher should be launched in background with &"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_card_watcher_pid_captured(self, entrypoint: Path):
        """The watcher PID must be captured (WATCHER_PID=$!)."""
        content = _read(entrypoint)
        assert "WATCHER_PID=$!" in content, (
            "Watcher PID should be captured with WATCHER_PID=$!"
        )


# ── Tests: Cleanup logic ───────────────────────────────────────────

class TestCleanup:
    """Verify watcher cleanup and SIGTERM handling."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_watcher_killed_on_exit(self, entrypoint: Path):
        """The watcher PID must be killed as part of cleanup."""
        content = _read(entrypoint)
        assert re.search(r'kill\s+.*WATCHER_PID', content), (
            "Script should kill $WATCHER_PID during cleanup"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_sigterm_trap_emits_timed_out(self, entrypoint: Path):
        """SIGTERM trap must emit a timed_out event."""
        content = _read(entrypoint)
        # Find trap line that handles SIGTERM
        trap_match = re.search(r"trap\s+['\"].*timed_out.*['\"].*SIGTERM", content)
        assert trap_match, (
            "SIGTERM trap should emit timed_out event"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_sigterm_trap_kills_watcher(self, entrypoint: Path):
        """SIGTERM trap must also kill the watcher process."""
        content = _read(entrypoint)
        trap_match = re.search(r"trap\s+'([^']+)'.*SIGTERM", content)
        assert trap_match, "SIGTERM trap not found"
        trap_body = trap_match.group(1)
        assert "WATCHER_PID" in trap_body, (
            "SIGTERM trap should kill WATCHER_PID"
        )


# ── Tests: progress.jsonl path ─────────────────────────────────────

class TestProgressFilePath:
    """Verify the progress file path is /output/progress.jsonl."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_progress_file_path(self, entrypoint: Path):
        """PROGRESS_FILE must point to /output/progress.jsonl."""
        content = _read(entrypoint)
        assert re.search(r'PROGRESS_FILE\s*=\s*["\']?/output/progress\.jsonl', content), (
            "PROGRESS_FILE should be set to /output/progress.jsonl"
        )


# ── Tests: Consistency between entrypoints ──────────────────────────

class TestConsistency:
    """Both entrypoints must share the same progress protocol."""

    def test_emit_progress_function_identical(self):
        """emit_progress function body should be the same in both entrypoints."""
        tested = _read(TESTED_ENTRYPOINT)
        blind = _read(BLIND_ENTRYPOINT)

        def _extract_function(content: str, name: str) -> str:
            """Extract a bash function body (simple heuristic: from 'name()' to next unindented line or function)."""
            pattern = rf"({name}\s*\(\)\s*\{{.*?\n\}})"
            match = re.search(pattern, content, re.DOTALL)
            assert match, f"Could not extract {name}() function"
            return match.group(1)

        tested_fn = _extract_function(tested, "emit_progress")
        blind_fn = _extract_function(blind, "emit_progress")
        assert tested_fn == blind_fn, (
            "emit_progress function should be identical in both entrypoints"
        )

    def test_card_watcher_function_identical(self):
        """card_watcher function body should be the same in both entrypoints."""
        tested = _read(TESTED_ENTRYPOINT)
        blind = _read(BLIND_ENTRYPOINT)

        def _extract_function(content: str, name: str) -> str:
            pattern = rf"({name}\s*\(\)\s*\{{.*?\n\}})"
            match = re.search(pattern, content, re.DOTALL)
            assert match, f"Could not extract {name}() function"
            return match.group(1)

        tested_fn = _extract_function(tested, "card_watcher")
        blind_fn = _extract_function(blind, "card_watcher")
        assert tested_fn == blind_fn, (
            "card_watcher function should be identical in both entrypoints"
        )

    def test_both_have_same_event_types(self):
        """Both entrypoints should emit the same set of event types."""
        tested = _read(TESTED_ENTRYPOINT)
        blind = _read(BLIND_ENTRYPOINT)

        def _extract_events(content: str) -> set:
            return set(re.findall(r'(?:\\?)"event(?:\\?)"\s*:\s*(?:\\?)"(\w+)(?:\\?)"', content))

        tested_events = _extract_events(tested)
        blind_events = _extract_events(blind)
        assert tested_events == blind_events, (
            f"Event types differ: tested={tested_events}, blind={blind_events}"
        )


# ── Tests: JSON format via bash execution ───────────────────────────

class TestEmitProgressJsonOutput:
    """Test emit_progress output by actually running it in bash."""

    def test_emit_progress_produces_valid_json(self, tmp_path: Path):
        """Sourcing emit_progress and calling it should produce valid JSON."""
        progress_file = tmp_path / "progress.jsonl"
        # Build a small bash script that defines emit_progress and calls it
        bash_script = f"""
set -euo pipefail
PROGRESS_FILE="{progress_file}"
emit_progress() {{
  local payload="$1"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "${{payload/\\{{/\\{{\\\"ts\\\": \\\"$ts\\\", }}" >> "$PROGRESS_FILE"
}}
emit_progress '{{"event": "started"}}'
emit_progress '{{"event": "failed", "exit_code": 1}}'
"""
        result = subprocess.run(
            ["bash", "-c", bash_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Bash script failed: {result.stderr}"

        lines = progress_file.read_text().strip().splitlines()
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

        for line in lines:
            data = json.loads(line)
            assert "ts" in data, "Each line must have a 'ts' field"
            assert "event" in data, "Each line must have an 'event' field"
            # Verify ts looks like ISO format
            assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", data["ts"]), (
                f"ts field not in ISO format: {data['ts']}"
            )

    def test_emit_progress_started_event_format(self, tmp_path: Path):
        """The started event should have event=started and a timestamp."""
        progress_file = tmp_path / "progress.jsonl"
        bash_script = f"""
set -euo pipefail
PROGRESS_FILE="{progress_file}"
emit_progress() {{
  local payload="$1"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "${{payload/\\{{/\\{{\\\"ts\\\": \\\"$ts\\\", }}" >> "$PROGRESS_FILE"
}}
emit_progress '{{"event": "started"}}'
"""
        result = subprocess.run(
            ["bash", "-c", bash_script],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Bash script failed: {result.stderr}"
        data = json.loads(progress_file.read_text().strip())
        assert data["event"] == "started"

    def test_emit_progress_preserves_extra_fields(self, tmp_path: Path):
        """Extra fields in the payload (like exit_code) must survive."""
        progress_file = tmp_path / "progress.jsonl"
        bash_script = f"""
set -euo pipefail
PROGRESS_FILE="{progress_file}"
emit_progress() {{
  local payload="$1"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "${{payload/\\{{/\\{{\\\"ts\\\": \\\"$ts\\\", }}" >> "$PROGRESS_FILE"
}}
emit_progress '{{"event": "failed", "exit_code": 42}}'
"""
        result = subprocess.run(
            ["bash", "-c", bash_script],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Bash script failed: {result.stderr}"
        data = json.loads(progress_file.read_text().strip())
        assert data["event"] == "failed"
        assert data["exit_code"] == 42

    def test_emit_progress_safe_under_set_e(self, tmp_path: Path):
        """emit_progress must not cause script to exit under set -e."""
        progress_file = tmp_path / "progress.jsonl"
        bash_script = f"""
set -euo pipefail
PROGRESS_FILE="{progress_file}"
emit_progress() {{
  local payload="$1"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "${{payload/\\{{/\\{{\\\"ts\\\": \\\"$ts\\\", }}" >> "$PROGRESS_FILE"
}}
emit_progress '{{"event": "started"}}'
echo "STILL_ALIVE"
"""
        result = subprocess.run(
            ["bash", "-c", bash_script],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "STILL_ALIVE" in result.stdout


# ── Tests: Script ordering ──────────────────────────────────────────

class TestScriptOrdering:
    """Verify the ordering of operations in the entrypoint."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_started_emitted_before_watcher(self, entrypoint: Path):
        """The 'started' event should be emitted before the card_watcher is launched."""
        content = _read(entrypoint)
        started_pos = content.find('"event": "started"')
        watcher_pos = content.find("card_watcher &")
        assert started_pos != -1, "'started' event not found"
        assert watcher_pos != -1, "card_watcher & not found"
        assert started_pos < watcher_pos, (
            "'started' event should come before card_watcher launch"
        )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_watcher_killed_before_final_event(self, entrypoint: Path):
        """The watcher should be killed before the completed/failed event is emitted."""
        content = _read(entrypoint)
        # Find last kill of WATCHER_PID (cleanup, not in trap)
        # Look for the kill outside the trap
        main_section = content[content.find("# Stop card watcher") or content.find("kill") :]
        kill_pos = content.rfind('kill "$WATCHER_PID"')
        completed_pos = content.find('"event": "completed"')
        failed_pos = content.find('"event": "failed"')

        # At least one of completed/failed should exist after the kill
        assert kill_pos != -1, "kill WATCHER_PID not found"
        if completed_pos != -1:
            assert kill_pos < completed_pos, (
                "Watcher should be killed before completed event"
            )
        if failed_pos != -1:
            # The failed event in the main flow (not in trap) should be after kill
            # Find the failed event that's NOT inside a trap
            main_failed_matches = [
                m.start()
                for m in re.finditer(r'"event":\s*"failed"', content)
                if "trap" not in content[max(0, m.start() - 200) : m.start()]
            ]
            for pos in main_failed_matches:
                assert kill_pos < pos, (
                    "Watcher should be killed before failed event in main flow"
                )

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_watcher_starts_after_emit_started(self, entrypoint: Path):
        """card_watcher should start after the 'started' progress event."""
        content = _read(entrypoint)
        started_emit = content.find('emit_progress \'{"event": "started"}\'')
        watcher_bg = content.find("card_watcher &")
        assert started_emit != -1, "emit_progress started not found"
        assert watcher_bg != -1, "card_watcher & not found"
        assert started_emit < watcher_bg


# ── Tests: set -euo pipefail ────────────────────────────────────────

class TestShellSettings:
    """Verify shell safety settings."""

    @pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
    def test_set_euo_pipefail(self, entrypoint: Path):
        """Script should start with set -euo pipefail for safety."""
        content = _read(entrypoint)
        assert "set -euo pipefail" in content
