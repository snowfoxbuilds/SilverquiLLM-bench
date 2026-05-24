"""Tests for direct streaming of docker_stdout.log / docker_stderr.log to run_dir.

Validates TODO item 11 requirements:
- _drain_pipe writes directly to run_dir/docker_stdout.log (no .tmp intermediate)
- No post-exit shutil.copy2 step from .tmp → .log
- Lines appear in run_dir file in real time
- _harvest_results skips docker_stdout.log / docker_stderr.log when already in run_dir
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.runner import ContainerLifecycle, LifecycleResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_popen(
    *,
    stdout_data: bytes = b"hello\n",
    stderr_data: bytes = b"",
    exit_code: int = 0,
    exit_delay: float = 0.0,
):
    """Build a mock Popen whose stdout/stderr behave like real pipes."""
    mock_proc = MagicMock()
    mock_proc.stdout = io.BytesIO(stdout_data)
    mock_proc.stderr = io.BytesIO(stderr_data)

    _start = time.monotonic()

    def _poll():
        if exit_delay and (time.monotonic() - _start) < exit_delay:
            return None
        return exit_code

    mock_proc.poll = MagicMock(side_effect=_poll)
    mock_proc.wait = MagicMock(return_value=exit_code)
    mock_proc.kill = MagicMock()
    return mock_proc


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture()
def output(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    rd = tmp_path / "run_dir"
    rd.mkdir()
    return rd


# ---------------------------------------------------------------------------
# ContainerLifecycle.run() — direct stream to run_dir
# ---------------------------------------------------------------------------


class TestRunDirectStreamToRunDir:
    """Exercises ContainerLifecycle.run() to verify direct streaming to run_dir."""

    def test_stdout_appears_in_run_dir(self, workspace, output, run_dir):
        """docker_stdout.log is written to run_dir during run()."""
        mock_proc = _make_mock_popen(stdout_data=b"stdout content\n", exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                run_dir=run_dir,
            )
            lc.run()

        log_file = run_dir / "docker_stdout.log"
        assert log_file.exists(), "docker_stdout.log should be in run_dir"
        assert "stdout content" in log_file.read_text(encoding="utf-8")

    def test_stderr_appears_in_run_dir(self, workspace, output, run_dir):
        """docker_stderr.log is written to run_dir during run()."""
        mock_proc = _make_mock_popen(
            stdout_data=b"out\n", stderr_data=b"err content\n",
            exit_code=0, exit_delay=0.1,
        )

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                run_dir=run_dir,
            )
            lc.run()

        log_file = run_dir / "docker_stderr.log"
        assert log_file.exists(), "docker_stderr.log should be in run_dir"
        assert "err content" in log_file.read_text(encoding="utf-8")

    def test_no_output_log_copy_when_run_dir_set(self, workspace, output, run_dir):
        """output/docker_stdout.log should NOT be created via copy when run_dir is set."""
        mock_proc = _make_mock_popen(stdout_data=b"data\n", exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                run_dir=run_dir,
            )
            lc.run()

        assert not (output / "docker_stdout.log").exists()
        assert not (output / "docker_stderr.log").exists()

    def test_no_tmp_files_when_run_dir_set(self, workspace, output, run_dir):
        """No .tmp intermediates should be created when run_dir is provided."""
        mock_proc = _make_mock_popen(stdout_data=b"data\n", exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                run_dir=run_dir,
            )
            lc.run()

        assert not (output / "docker_stdout.tmp").exists(), \
            ".tmp intermediates should not exist when run_dir streams directly"
        assert not (output / "docker_stderr.tmp").exists(), \
            ".tmp intermediates should not exist when run_dir streams directly"

    def test_multiline_output_fully_captured(self, workspace, output, run_dir):
        """All lines from container stdout appear in run_dir log."""
        data = b"line1\nline2\nline3\n"
        mock_proc = _make_mock_popen(stdout_data=data, exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                run_dir=run_dir,
            )
            lc.run()

        content = (run_dir / "docker_stdout.log").read_text(encoding="utf-8")
        assert "line1\n" in content
        assert "line2\n" in content
        assert "line3\n" in content

    def test_invalid_utf8_handled_with_replacement(self, workspace, output, run_dir):
        """Invalid UTF-8 in container output is replaced, not raised."""
        data = b"good\xff bad\n"
        mock_proc = _make_mock_popen(stdout_data=data, exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                run_dir=run_dir,
            )
            lc.run()

        text = (run_dir / "docker_stdout.log").read_text(encoding="utf-8")
        assert "good" in text
        assert "\ufffd" in text


# ---------------------------------------------------------------------------
# _harvest_results skip logic tests
# ---------------------------------------------------------------------------


class TestHarvestResultsSkipDirectStream:
    """Tests for _harvest_results skipping already-streamed files."""

    def test_harvest_skips_stdout_log_when_already_in_run_dir(self, tmp_path: Path):
        """_harvest_results does not overwrite docker_stdout.log if it already exists."""
        from silverquillm.cli import _harvest_results

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"
        output.mkdir()
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create the file in output (would normally be copied in old path)
        (output / "docker_stdout.log").write_text("from output", encoding="utf-8")
        (output / "docker_stderr.log").write_text("from output err", encoding="utf-8")

        # Pre-create in run_dir (simulating direct streaming)
        run_dir = results_dir / "test_run"
        run_dir.mkdir(parents=True)
        (run_dir / "docker_stdout.log").write_text("streamed live", encoding="utf-8")
        (run_dir / "docker_stderr.log").write_text("streamed live err", encoding="utf-8")

        with patch("silverquillm.cli.build_card_name_map", return_value={}), \
             patch("silverquillm.cli._write_card_statuses"):
            _harvest_results(
                workspace=workspace,
                output=output,
                results_dir=results_dir,
                run_name="test_run",
            )

        # The files should NOT be overwritten by harvest
        assert (run_dir / "docker_stdout.log").read_text(encoding="utf-8") == "streamed live"
        assert (run_dir / "docker_stderr.log").read_text(encoding="utf-8") == "streamed live err"

