"""Tests for silverquillm.telemetry — FastTelemetry 1 Hz loop."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.telemetry import CHANNEL_FILES, FastTelemetry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def telemetry_dirs(tmp_path):
    """Create output_dir, run_dir, workspace_dir with realistic card/engine structure.

    Uses the real two-level layout: cards/{set}/{card_id}/card_impl.py
    e.g. cards/sos/sos_1/card_impl.py, cards/fdn/fdn_001/card_impl.py
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    # Create cards/sos/sos_1/card_impl.py (two-level: set/card_id/)
    sos_card_dir = workspace_dir / "cards" / "sos" / "sos_1"
    sos_card_dir.mkdir(parents=True)
    (sos_card_dir / "card_impl.py").write_text("# sos card impl")
    # Create cards/fdn/fdn_001/card_impl.py (two-level: set/card_id/)
    fdn_card_dir = workspace_dir / "cards" / "fdn" / "fdn_001"
    fdn_card_dir.mkdir(parents=True)
    (fdn_card_dir / "card_impl.py").write_text("# fdn card impl")
    # Create engine/core.py
    engine_dir = workspace_dir / "engine"
    engine_dir.mkdir()
    (engine_dir / "core.py").write_text("# engine core")
    return output_dir, run_dir, workspace_dir


@pytest.fixture
def ft(telemetry_dirs):
    """Create a FastTelemetry instance and ensure cleanup."""
    output_dir, run_dir, workspace_dir = telemetry_dirs
    ft = FastTelemetry(
        output_dir=output_dir,
        run_dir=run_dir,
        workspace_dir=workspace_dir,
    )
    yield ft
    ft.stop(timeout=2.0)


# ---------------------------------------------------------------------------
# Channel-to-file mapping
# ---------------------------------------------------------------------------


class TestChannelFiles:
    def test_progress_channel_maps_to_progress_jsonl(self):
        assert CHANNEL_FILES["progress"] == "progress.jsonl"

    def test_edit_channel_maps_to_fast_telemetry_jsonl(self):
        assert CHANNEL_FILES["edit"] == "fast_telemetry.jsonl"

    def test_system_channel_maps_to_system_log(self):
        assert CHANNEL_FILES["system"] == "system.log"


# ---------------------------------------------------------------------------
# Start / stop lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_starts_and_reports_running(self, ft):
        ft.start()
        assert ft.running is True

    def test_stops_cleanly_within_timeout(self, ft):
        ft.start()
        assert ft.running is True
        ft.stop(timeout=3.0)
        assert ft.running is False

    def test_start_is_idempotent(self, ft):
        ft.start()
        thread_id = ft._thread.ident
        ft.start()  # second start should be a no-op
        assert ft._thread.ident == thread_id

    def test_thread_is_daemon(self, ft):
        ft.start()
        assert ft._thread.daemon is True


# ---------------------------------------------------------------------------
# Progress tailing
# ---------------------------------------------------------------------------


class TestProgressTailing:
    def test_detects_new_lines_in_progress_jsonl(self, ft, telemetry_dirs):
        output_dir, run_dir, _ = telemetry_dirs
        # Write progress data before starting
        progress_file = output_dir / "progress.jsonl"
        progress_file.write_text('{"step": 1}\n{"step": 2}\n')

        ft.start()
        # Give the loop time to poll
        time.sleep(1.5)
        ft.stop()

        out_file = run_dir / "progress.jsonl"
        assert out_file.exists()
        lines = out_file.read_text().strip().split("\n")
        assert '{"step": 1}' in lines
        assert '{"step": 2}' in lines

    def test_detects_appended_lines_after_start(self, ft, telemetry_dirs):
        output_dir, run_dir, _ = telemetry_dirs
        progress_file = output_dir / "progress.jsonl"
        progress_file.write_text("")

        ft.start()
        time.sleep(0.3)
        # Append a line while running
        with open(progress_file, "a") as f:
            f.write('{"step": "appended"}\n')
        time.sleep(1.5)
        ft.stop()

        out_file = run_dir / "progress.jsonl"
        assert out_file.exists()
        content = out_file.read_text()
        assert '{"step": "appended"}' in content

    def test_handles_missing_progress_file_gracefully(self, ft, telemetry_dirs):
        """Should not crash if progress.jsonl doesn't exist yet."""
        _, run_dir, _ = telemetry_dirs
        ft.start()
        time.sleep(1.5)
        ft.stop()
        # No crash, and output file may or may not exist (no data to write)
        assert ft.running is False


# ---------------------------------------------------------------------------
# System log tailing
# ---------------------------------------------------------------------------


class TestSystemLogTailing:
    def test_detects_new_lines_in_system_log(self, ft, telemetry_dirs):
        output_dir, run_dir, _ = telemetry_dirs
        system_file = output_dir / "system.log"
        system_file.write_text("boot complete\nagent started\n")

        ft.start()
        time.sleep(1.5)
        ft.stop()

        out_file = run_dir / "system.log"
        assert out_file.exists()
        lines = out_file.read_text().strip().split("\n")
        assert "boot complete" in lines
        assert "agent started" in lines


# ---------------------------------------------------------------------------
# Mtime edit detection
# ---------------------------------------------------------------------------


class TestMtimeEditDetection:
    def test_detects_mtime_change_on_sos_card_impl(self, ft, telemetry_dirs):
        _, run_dir, workspace_dir = telemetry_dirs
        card_impl = workspace_dir / "cards" / "sos" / "sos_1" / "card_impl.py"

        ft.start()
        # Let first poll record initial mtimes
        time.sleep(1.5)

        # Touch the file to change mtime
        time.sleep(0.05)
        card_impl.write_text("# modified sos card impl")
        time.sleep(1.5)
        ft.stop()

        out_file = run_dir / "fast_telemetry.jsonl"
        assert out_file.exists()
        lines = out_file.read_text().strip().split("\n")
        events = [json.loads(line) for line in lines if line]
        assert any(e["type"] == "edit" and "card_impl.py" in e["path"] for e in events)

    def test_detects_mtime_change_on_fdn_card_impl(self, ft, telemetry_dirs):
        _, run_dir, workspace_dir = telemetry_dirs
        card_impl = workspace_dir / "cards" / "fdn" / "fdn_001" / "card_impl.py"

        ft.start()
        # Let first poll record initial mtimes
        time.sleep(1.5)

        # Touch the file to change mtime
        time.sleep(0.05)
        card_impl.write_text("# modified fdn card impl")
        time.sleep(1.5)
        ft.stop()

        out_file = run_dir / "fast_telemetry.jsonl"
        assert out_file.exists()
        lines = out_file.read_text().strip().split("\n")
        events = [json.loads(line) for line in lines if line]
        assert any(e["type"] == "edit" and "card_impl.py" in e["path"] for e in events)

    def test_detects_mtime_change_on_engine_file(self, ft, telemetry_dirs):
        _, run_dir, workspace_dir = telemetry_dirs
        engine_file = workspace_dir / "engine" / "core.py"

        ft.start()
        time.sleep(1.5)

        time.sleep(0.05)
        engine_file.write_text("# modified engine")
        time.sleep(1.5)
        ft.stop()

        out_file = run_dir / "fast_telemetry.jsonl"
        assert out_file.exists()
        lines = out_file.read_text().strip().split("\n")
        events = [json.loads(line) for line in lines if line]
        assert any(e["type"] == "edit" and "core.py" in e["path"] for e in events)

    def test_no_edit_event_without_mtime_change(self, ft, telemetry_dirs):
        _, run_dir, _ = telemetry_dirs

        ft.start()
        time.sleep(2.5)
        ft.stop()

        out_file = run_dir / "fast_telemetry.jsonl"
        # File either doesn't exist or is empty (no edits detected)
        if out_file.exists():
            assert out_file.read_text().strip() == ""


# ---------------------------------------------------------------------------
# No Git operations
# ---------------------------------------------------------------------------


class TestNoGitOperations:
    def test_does_not_invoke_git(self, ft, telemetry_dirs):
        output_dir, _, workspace_dir = telemetry_dirs
        # Write data to trigger all channels
        (output_dir / "progress.jsonl").write_text('{"x":1}\n')
        (output_dir / "system.log").write_text("log line\n")

        with patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen") as mock_popen, \
             patch("subprocess.check_call") as mock_check:
            ft.start()
            time.sleep(1.5)
            # Touch a file to trigger edit events
            (workspace_dir / "cards" / "sos" / "sos_1" / "card_impl.py").write_text("# x")
            time.sleep(1.5)
            ft.stop()

            # Assert no subprocess calls (which would include git)
            mock_run.assert_not_called()
            mock_popen.assert_not_called()
            mock_check.assert_not_called()


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------


class TestCallback:
    def test_on_event_callback_invoked(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        (output_dir / "progress.jsonl").write_text('{"cb": true}\n')

        events = []
        ft = FastTelemetry(
            output_dir=output_dir,
            run_dir=run_dir,
            workspace_dir=workspace_dir,
            on_event=lambda ch, msg: events.append((ch, msg)),
        )
        ft.start()
        time.sleep(1.5)
        ft.stop()

        assert any(ch == "progress" for ch, _ in events)
