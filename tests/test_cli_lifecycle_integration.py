"""Tests for Item 6: ContainerLifecycle integration into CLI run/smoke commands.

Covers --hang-timeout option, ContainerLifecycle construction args for smoke,
harvest workspace_final/ materialization, timeout_reason propagation, and
glob-based output file harvesting.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from silverquillm.cli import main, _harvest_results
from silverquillm.runner import LifecycleResult


@pytest.fixture()
def runner():
    return CliRunner()


def _make_lifecycle_mock(exit_code=0, timed_out=False, timeout_reason=None):
    """Helper to create a mock ContainerLifecycle instance."""
    mock_instance = MagicMock()
    mock_instance.run.return_value = LifecycleResult(
        exit_code=exit_code,
        timed_out=timed_out,
        timeout_reason=timeout_reason,
        container_name="test",
    )
    return mock_instance


# ---------------------------------------------------------------------------
# --hang-timeout CLI option
# ---------------------------------------------------------------------------


class TestHangTimeoutOption:
    """The run command must accept --hang-timeout with default 900."""

    def test_run_help_shows_hang_timeout(self, runner):
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "--hang-timeout" in result.output

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_default_hang_timeout_is_900(self, mock_stage, mock_cls, runner, tmp_path):
        """Without --hang-timeout, ContainerLifecycle gets hang_timeout=900."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_cls.return_value = _make_lifecycle_mock()

        runner.invoke(main, ["run", "--image", "img"])
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("hang_timeout") == 900

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_custom_hang_timeout_passed_through(self, mock_stage, mock_cls, runner, tmp_path):
        """--hang-timeout 300 should be forwarded to ContainerLifecycle."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_cls.return_value = _make_lifecycle_mock()

        runner.invoke(main, ["run", "--image", "img", "--hang-timeout", "300"])
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("hang_timeout") == 300


# ---------------------------------------------------------------------------
# Smoke command ContainerLifecycle args
# ---------------------------------------------------------------------------


class TestSmokeLifecycleArgs:
    """Smoke command should use hard_timeout=120, hang_timeout=60, and sqm-smoke-{pid} name."""

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_hard_timeout_120(self, mock_cls, runner):
        mock_cls.return_value = _make_lifecycle_mock()
        runner.invoke(main, ["smoke", "--image", "img"])
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("hard_timeout") == 120

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_hang_timeout_60(self, mock_cls, runner):
        mock_cls.return_value = _make_lifecycle_mock()
        runner.invoke(main, ["smoke", "--image", "img"])
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("hang_timeout") == 60

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_container_name_pattern(self, mock_cls, runner):
        """Container name should be sqm-smoke-{pid}."""
        mock_cls.return_value = _make_lifecycle_mock()
        runner.invoke(main, ["smoke", "--image", "img"])
        call_kwargs = mock_cls.call_args
        name = call_kwargs.kwargs.get("container_name")
        assert name is not None
        assert name.startswith("sqm-smoke-")
        # The suffix should be the PID (an integer)
        pid_part = name.split("sqm-smoke-")[1]
        assert pid_part.isdigit()

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_timeout_exits_nonzero(self, mock_cls, runner):
        """Smoke should exit 1 if the container times out."""
        mock_cls.return_value = _make_lifecycle_mock(
            exit_code=None, timed_out=True, timeout_reason="hard_timeout"
        )
        result = runner.invoke(main, ["smoke", "--image", "img"])
        assert result.exit_code != 0
        assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# Harvest: workspace_final/ materialization
# ---------------------------------------------------------------------------


class TestHarvestWorkspaceFinal:
    """_harvest_results should create workspace_final/ as a snapshot of workspace."""

    def test_workspace_final_created(self, tmp_path):
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Put a file in workspace to verify it appears in snapshot
        (workspace / "somefile.txt").write_text("hello")

        run_dir = _harvest_results(workspace, output, results, "test-run", timed_out=False)

        wf = run_dir / "workspace_final"
        assert wf.is_dir(), "workspace_final/ should be created"
        assert (wf / "somefile.txt").read_text() == "hello"

    def test_workspace_final_excludes_pycache(self, tmp_path):
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        pycache = workspace / "__pycache__"
        pycache.mkdir()
        (pycache / "mod.pyc").write_text("bytecode")

        run_dir = _harvest_results(workspace, output, results, "test-run", timed_out=False)

        wf = run_dir / "workspace_final"
        assert not (wf / "__pycache__").exists(), "__pycache__ should be excluded"


# ---------------------------------------------------------------------------
# Harvest: timeout_reason parameter
# ---------------------------------------------------------------------------


class TestHarvestTimeoutReason:
    """_harvest_results should accept and use timeout_reason."""

    def test_timeout_reason_accepted(self, tmp_path):
        """Should not raise when timeout_reason is passed."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=True, timeout_reason="hang_timeout",
        )
        assert run_dir.exists()

    def test_timeout_reason_none_accepted(self, tmp_path):
        """Should work fine with timeout_reason=None (default)."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        run_dir = _harvest_results(
            workspace, output, results, "test-run",
            timed_out=False, timeout_reason=None,
        )
        assert run_dir.exists()


# ---------------------------------------------------------------------------
# Harvest: glob output files (*.log, *.jsonl)
# ---------------------------------------------------------------------------


class TestHarvestGlobOutputFiles:
    """Harvest should copy all *.log and *.jsonl files from output dir."""

    def test_arbitrary_log_files_harvested(self, tmp_path):
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        (output / "system.log").write_text("system log content\n")
        (output / "agent_stdout.log").write_text("agent output\n")
        (output / "custom.jsonl").write_text('{"event": "test"}\n')
        # Non-matching files should NOT be copied
        (output / "notes.txt").write_text("should not appear\n")

        run_dir = _harvest_results(workspace, output, results, "test-run", timed_out=False)

        assert (run_dir / "system.log").read_text() == "system log content\n"
        assert (run_dir / "agent_stdout.log").read_text() == "agent output\n"
        assert (run_dir / "custom.jsonl").read_text() == '{"event": "test"}\n'
        assert not (run_dir / "notes.txt").exists()


# ---------------------------------------------------------------------------
# Harvest: run_manifest.json from workspace_final
# ---------------------------------------------------------------------------


class TestHarvestManifestFromWorkspaceFinal:
    """run_manifest.json should be copied from workspace_final snapshot to results dir."""

    def test_manifest_harvested_from_workspace_final(self, tmp_path):
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        manifest = {"timeout_seconds": 600, "deadline_utc": "2025-01-01T00:10:00Z"}
        (workspace / "run_manifest.json").write_text(json.dumps(manifest))

        run_dir = _harvest_results(workspace, output, results, "test-run", timed_out=False)

        # Manifest should exist at top-level results AND in workspace_final
        assert (run_dir / "run_manifest.json").exists()
        assert (run_dir / "workspace_final" / "run_manifest.json").exists()
        assert json.loads((run_dir / "run_manifest.json").read_text()) == manifest


# ---------------------------------------------------------------------------
# Run command: ContainerLifecycle.run() is called (not subprocess.run)
# ---------------------------------------------------------------------------


class TestRunUsesLifecycle:
    """The run command must use ContainerLifecycle, not subprocess.run directly."""

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_lifecycle_run_called(self, mock_stage, mock_cls, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_cls.return_value = _make_lifecycle_mock()

        runner.invoke(main, ["run", "--image", "img"])
        mock_cls.return_value.run.assert_called_once()

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_run_nonzero_exit_reports_error(self, mock_stage, mock_cls, runner, tmp_path):
        """Non-zero exit code should be reported in stderr."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_cls.return_value = _make_lifecycle_mock(exit_code=42)

        result = runner.invoke(main, ["run", "--image", "img"])
        assert "42" in result.output or "exit code" in result.output.lower()

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_run_hang_timeout_reports_reason(self, mock_stage, mock_cls, runner, tmp_path):
        """hang_timeout should be reported when container hangs."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_cls.return_value = _make_lifecycle_mock(
            exit_code=None, timed_out=True, timeout_reason="hang_timeout"
        )

        result = runner.invoke(main, ["run", "--image", "img"])
        assert "hang_timeout" in result.output.lower() or "timed out" in result.output.lower()
