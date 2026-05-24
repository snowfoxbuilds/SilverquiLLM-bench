"""Tests for the _runner_log helper in cli.py.

Verifies that:
- _runner_log(msg) calls click.echo(msg) with err=False
- _runner_log(msg, err=True) calls click.echo(msg, err=True)
- Each call appends an ISO-8601 timestamped line to run_dir/runner.log
- When err=True, also appends to run_dir/runner_errors.log
- When err=False, runner_errors.log is NOT written to
- Multiple calls append (not overwrite)
- Timestamp format is valid ISO-8601
- Gracefully handles missing run_dir (no crash)
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ISO8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00 .+$"
)


def _get_runner_log():
    """Import _runner_log and the module-level variable setter."""
    import silverquillm.cli as cli_mod
    return cli_mod._runner_log, cli_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunnerLogEcho:
    """Verify click.echo is called correctly."""

    def test_echo_called_with_msg(self):
        func, cli_mod = _get_runner_log()
        with patch.object(cli_mod, "click") as mock_click:
            # Ensure log_dir is None so file writes are skipped
            cli_mod._runner_log_dir = None
            func("hello world")
            mock_click.echo.assert_called_once_with("hello world", err=False)

    def test_echo_called_with_err_true(self):
        func, cli_mod = _get_runner_log()
        with patch.object(cli_mod, "click") as mock_click:
            cli_mod._runner_log_dir = None
            func("error msg", err=True)
            mock_click.echo.assert_called_once_with("error msg", err=True)

    def test_echo_err_defaults_false(self):
        func, cli_mod = _get_runner_log()
        with patch.object(cli_mod, "click") as mock_click:
            cli_mod._runner_log_dir = None
            func("info")
            mock_click.echo.assert_called_once_with("info", err=False)


class TestRunnerLogFileWrites:
    """Verify file append behaviour."""

    def test_appends_to_runner_log(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path
        with patch.object(cli_mod, "click"):
            func("test message")
        log_file = tmp_path / "runner.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content

    def test_runner_log_has_iso8601_timestamp(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path
        with patch.object(cli_mod, "click"):
            func("timestamped")
        log_file = tmp_path / "runner.log"
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert ISO8601_PATTERN.match(lines[0])

    def test_err_true_writes_to_errors_log(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path
        with patch.object(cli_mod, "click"):
            func("bad thing", err=True)
        err_file = tmp_path / "runner_errors.log"
        assert err_file.exists()
        content = err_file.read_text(encoding="utf-8")
        assert "bad thing" in content

    def test_err_true_also_writes_to_runner_log(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path
        with patch.object(cli_mod, "click"):
            func("error info", err=True)
        log_file = tmp_path / "runner.log"
        assert log_file.exists()
        assert "error info" in log_file.read_text(encoding="utf-8")

    def test_err_false_does_not_write_errors_log(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path
        with patch.object(cli_mod, "click"):
            func("normal message")
        err_file = tmp_path / "runner_errors.log"
        assert not err_file.exists()

    def test_multiple_calls_append(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path
        with patch.object(cli_mod, "click"):
            func("first")
            func("second")
            func("third")
        log_file = tmp_path / "runner.log"
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        assert "first" in lines[0]
        assert "second" in lines[1]
        assert "third" in lines[2]


class TestRunnerLogMissingDir:
    """Verify graceful handling when run_dir is None or missing."""

    def test_no_crash_when_log_dir_is_none(self):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = None
        with patch.object(cli_mod, "click"):
            # Should not raise
            func("should not crash")

    def test_no_crash_when_log_dir_does_not_exist(self, tmp_path):
        func, cli_mod = _get_runner_log()
        cli_mod._runner_log_dir = tmp_path / "nonexistent"
        with patch.object(cli_mod, "click"):
            # Should not raise
            func("should not crash either")
