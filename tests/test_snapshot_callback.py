"""Tests for the snapshot_callback closure wired in cli.py's run command.

Exercises the REAL callback produced by cli.py's `run` command by:
- Using Click's CliRunner to invoke `run` with ContainerLifecycle mocked
- Capturing the `snapshot_callback` kwarg passed to ContainerLifecycle
- Calling the captured callback and verifying its behaviour

Verifies that:
- The callback writes valid JSON lines to snapshot_telemetry.jsonl
- Each record contains required fields with correct types (ts, snapshot_index, files_changed, elapsed_s)
- Multiple invocations append multiple lines
- snapshot_index increments on each call
- _display.emit_snapshot(snapshot_index) is called when display is available
- No error when display is None
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import pytest
from click.testing import CliRunner

from silverquillm.runner import LifecycleResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lifecycle_result() -> LifecycleResult:
    """Create a successful LifecycleResult for mocking."""
    return LifecycleResult(
        exit_code=0,
        timed_out=False,
        timeout_reason=None,
        container_name="sqm-test",
    )


def _invoke_run_and_capture_callback(tmp_path: Path) -> tuple:
    """Invoke cli.run via CliRunner, mock heavy deps, return captured snapshot_callback and run_dir.

    Returns (snapshot_callback, run_dir, output_dir).
    """
    from silverquillm.cli import main

    captured = {}

    # Mock ContainerLifecycle to capture snapshot_callback
    mock_lifecycle_cls = MagicMock()
    mock_lifecycle_instance = MagicMock()
    mock_lifecycle_instance.run.return_value = _make_lifecycle_result()
    mock_lifecycle_cls.return_value = mock_lifecycle_instance

    # Mock stage_workspace to use tmp_path dirs
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "cards").mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    def fake_stage_workspace(output_dir=None, card_filter=None):
        return workspace_dir, output_dir

    results_dir = tmp_path / "results"
    results_dir.mkdir()

    with patch("silverquillm.cli.ContainerLifecycle", mock_lifecycle_cls), \
         patch("silverquillm.cli.stage_workspace", side_effect=fake_stage_workspace), \
         patch("silverquillm.cli._harvest_results", return_value=results_dir / "run"), \
         patch("silverquillm.cli._evaluate_results"), \
         patch("silverquillm.cli._generate_run_summary"), \
         patch("silverquillm.cli.build_card_name_map", return_value={}), \
         patch("silverquillm.cli._api_key_env_args", return_value=[]):

        runner = CliRunner()
        result = runner.invoke(main, [
            "run",
            "--image", "test-image:latest",
            "--timeout", "60",
            "--results-dir", str(results_dir),
        ])

    # Extract the snapshot_callback from the ContainerLifecycle call
    assert mock_lifecycle_cls.called, "ContainerLifecycle was not instantiated"
    call_kwargs = mock_lifecycle_cls.call_args[1] if mock_lifecycle_cls.call_args[1] else {}
    # Try keyword args first, then positional
    if "snapshot_callback" in call_kwargs:
        cb = call_kwargs["snapshot_callback"]
    else:
        # snapshot_callback might be positional — unlikely but check
        call_args = mock_lifecycle_cls.call_args[0]
        cb = None
        for arg in call_args:
            if callable(arg):
                cb = arg
                break

    # Find the run_dir that was created
    # It's passed as kwarg to ContainerLifecycle
    run_dir = call_kwargs.get("run_dir")

    return cb, run_dir, output_dir, result


# ---------------------------------------------------------------------------
# Tests: callback is wired (not None) and writes correct telemetry
# ---------------------------------------------------------------------------


class TestSnapshotCallbackWiring:
    """Verify cli.run passes a non-None snapshot_callback to ContainerLifecycle."""

    def test_container_lifecycle_receives_callable_snapshot_callback(self, tmp_path):
        cb, run_dir, output_dir, cli_result = _invoke_run_and_capture_callback(tmp_path)
        assert cb is not None, "snapshot_callback should not be None"
        assert callable(cb), "snapshot_callback should be callable"

    def test_run_dir_is_passed_to_lifecycle(self, tmp_path):
        cb, run_dir, output_dir, cli_result = _invoke_run_and_capture_callback(tmp_path)
        assert run_dir is not None, "run_dir should be passed to ContainerLifecycle"


class TestSnapshotCallbackWritesJsonl:
    """Verify snapshot_telemetry.jsonl is populated correctly by the real callback."""

    def test_single_invocation_creates_telemetry_file(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        assert run_dir is not None
        # Ensure run_dir exists (it should have been created by cli)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        assert telemetry_file.exists(), "snapshot_telemetry.jsonl should be created"
        lines = telemetry_file.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_record_has_all_required_fields(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        record = json.loads(telemetry_file.read_text().strip())
        assert "ts" in record, "record must have 'ts' field"
        assert "snapshot_index" in record, "record must have 'snapshot_index' field"
        assert "files_changed" in record, "record must have 'files_changed' field"
        assert "elapsed_s" in record, "record must have 'elapsed_s' field"

    def test_ts_is_valid_iso8601_with_timezone(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        record = json.loads(telemetry_file.read_text().strip())
        parsed = datetime.fromisoformat(record["ts"])
        assert parsed.tzinfo is not None, "ts should be timezone-aware"

    def test_snapshot_index_is_int(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        record = json.loads(telemetry_file.read_text().strip())
        assert isinstance(record["snapshot_index"], int)

    def test_files_changed_is_int(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        record = json.loads(telemetry_file.read_text().strip())
        assert isinstance(record["files_changed"], int)

    def test_elapsed_s_is_float(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        record = json.loads(telemetry_file.read_text().strip())
        assert isinstance(record["elapsed_s"], (int, float))

    def test_snapshot_index_increments_on_each_call(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()
        cb()
        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        lines = telemetry_file.read_text().strip().splitlines()
        indices = [json.loads(line)["snapshot_index"] for line in lines]
        assert indices == [1, 2, 3]

    def test_multiple_calls_append_lines(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        for _ in range(5):
            cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        lines = telemetry_file.read_text().strip().splitlines()
        assert len(lines) == 5

    def test_elapsed_s_increases_over_calls(self, tmp_path):
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        cb()
        time.sleep(0.05)
        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        lines = telemetry_file.read_text().strip().splitlines()
        elapsed_values = [json.loads(line)["elapsed_s"] for line in lines]
        assert elapsed_values[1] > elapsed_values[0]


class TestSnapshotCallbackEmitSnapshot:
    """Verify _display.emit_snapshot() is called when display is available."""

    def test_emit_snapshot_called_with_snapshot_index(self, tmp_path):
        """When a TUI display object is available, emit_snapshot should be called."""
        from silverquillm.cli import main

        mock_lifecycle_cls = MagicMock()
        mock_lifecycle_instance = MagicMock()
        mock_lifecycle_instance.run.return_value = _make_lifecycle_result()
        mock_lifecycle_cls.return_value = mock_lifecycle_instance

        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "cards").mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        mock_display = MagicMock()

        def fake_stage_workspace(output_dir=None, card_filter=None):
            return workspace_dir, output_dir

        with patch("silverquillm.cli.ContainerLifecycle", mock_lifecycle_cls), \
             patch("silverquillm.cli.stage_workspace", side_effect=fake_stage_workspace), \
             patch("silverquillm.cli._harvest_results", return_value=results_dir / "run"), \
             patch("silverquillm.cli._evaluate_results"), \
             patch("silverquillm.cli._generate_run_summary"), \
             patch("silverquillm.cli.build_card_name_map", return_value={}), \
             patch("silverquillm.cli._api_key_env_args", return_value=[]), \
             patch("silverquillm.cli._display", mock_display, create=True):

            runner = CliRunner()
            result = runner.invoke(main, [
                "run",
                "--image", "test-image:latest",
                "--timeout", "60",
                "--results-dir", str(results_dir),
            ])

        # Get the callback and call it
        call_kwargs = mock_lifecycle_cls.call_args[1]
        cb = call_kwargs["snapshot_callback"]
        assert cb is not None

        # Make run_dir exist
        run_dir = Path(call_kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        # Patch _display at the module level so the closure sees it
        with patch("silverquillm.cli._display", mock_display, create=True):
            cb()

        mock_display.emit_snapshot.assert_called_once_with(1)

    def test_no_error_when_display_is_none(self, tmp_path):
        """When display is None, callback should still work without error."""
        cb, run_dir, output_dir, _ = _invoke_run_and_capture_callback(tmp_path)
        Path(run_dir).mkdir(parents=True, exist_ok=True)

        # _display is not set / is None in the test context — callback should not raise
        cb()

        telemetry_file = Path(run_dir) / "snapshot_telemetry.jsonl"
        assert telemetry_file.exists()
        record = json.loads(telemetry_file.read_text().strip())
        assert record["snapshot_index"] == 1
