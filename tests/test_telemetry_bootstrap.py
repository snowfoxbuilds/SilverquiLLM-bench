"""Tests for FastTelemetry bootstrap event emission on first _poll_mtimes pass."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from silverquillm.telemetry import FastTelemetry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def telemetry_dirs(tmp_path):
    """Create output_dir, run_dir, workspace_dir with card/engine files."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    # cards/sos/sos_1/card_impl.py
    sos_dir = workspace_dir / "cards" / "sos" / "sos_1"
    sos_dir.mkdir(parents=True)
    (sos_dir / "card_impl.py").write_text("# sos")
    # engine/core.py
    engine_dir = workspace_dir / "engine"
    engine_dir.mkdir()
    (engine_dir / "core.py").write_text("# engine")
    return output_dir, run_dir, workspace_dir


@pytest.fixture
def empty_workspace(tmp_path):
    """Workspace with no watched files (no cards/ or engine/ dirs)."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    return output_dir, run_dir, workspace_dir


# ---------------------------------------------------------------------------
# Bootstrap emission tests
# ---------------------------------------------------------------------------


class TestBootstrapEmission:
    """Verify bootstrap event is emitted on first _poll_mtimes call."""

    def test_first_poll_emits_bootstrap_event(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        assert out_file.exists()
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        events = [json.loads(l) for l in lines]
        bootstrap_events = [e for e in events if e.get("event") == "bootstrap"]
        assert len(bootstrap_events) == 1

    def test_bootstrap_has_correct_event_field(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        bootstrap = next(
            json.loads(l) for l in lines if json.loads(l).get("event") == "bootstrap"
        )
        assert bootstrap["event"] == "bootstrap"

    def test_bootstrap_ts_is_iso8601(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        before = datetime.now(timezone.utc)
        ft._poll_mtimes()
        after = datetime.now(timezone.utc)

        out_file = run_dir / "fast_telemetry.jsonl"
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        bootstrap = next(
            json.loads(l) for l in lines if json.loads(l).get("event") == "bootstrap"
        )
        # Should parse as ISO-8601
        ts = datetime.fromisoformat(bootstrap["ts"])
        assert before <= ts <= after

    def test_bootstrap_files_seen_is_int(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        bootstrap = next(
            json.loads(l) for l in lines if json.loads(l).get("event") == "bootstrap"
        )
        assert isinstance(bootstrap["files_seen"], int)

    def test_bootstrap_files_seen_matches_actual_count(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        bootstrap = next(
            json.loads(l) for l in lines if json.loads(l).get("event") == "bootstrap"
        )
        # We have 2 files: cards/sos/sos_1/card_impl.py and engine/core.py
        assert bootstrap["files_seen"] == 2

    def test_bootstrap_poll_interval_s_is_float(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        bootstrap = next(
            json.loads(l) for l in lines if json.loads(l).get("event") == "bootstrap"
        )
        assert isinstance(bootstrap["poll_interval_s"], (int, float))
        assert bootstrap["poll_interval_s"] > 0

    def test_bootstrap_emitted_only_once(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()
        ft._poll_mtimes()
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        events = [json.loads(l) for l in lines]
        bootstrap_events = [e for e in events if e.get("event") == "bootstrap"]
        assert len(bootstrap_events) == 1

    def test_subsequent_poll_no_bootstrap_only_edits(self, telemetry_dirs):
        output_dir, run_dir, workspace_dir = telemetry_dirs
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        # Clear the file to isolate second poll output
        out_file = run_dir / "fast_telemetry.jsonl"
        out_file.write_text("")

        # Touch a file to trigger an edit event
        time.sleep(0.05)
        card = workspace_dir / "cards" / "sos" / "sos_1" / "card_impl.py"
        card.write_text("# modified")

        ft._poll_mtimes()

        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        events = [json.loads(l) for l in lines]
        # No bootstrap in second pass
        assert not any(e.get("event") == "bootstrap" for e in events)
        # Should have an edit event
        assert any(e.get("type") == "edit" for e in events)

    def test_bootstrap_files_seen_zero_when_no_files(self, empty_workspace):
        output_dir, run_dir, workspace_dir = empty_workspace
        ft = FastTelemetry(
            output_dir=output_dir, run_dir=run_dir, workspace_dir=workspace_dir
        )
        ft._poll_mtimes()

        out_file = run_dir / "fast_telemetry.jsonl"
        assert out_file.exists()
        lines = [l for l in out_file.read_text().strip().split("\n") if l]
        bootstrap = next(
            json.loads(l) for l in lines if json.loads(l).get("event") == "bootstrap"
        )
        assert bootstrap["files_seen"] == 0
