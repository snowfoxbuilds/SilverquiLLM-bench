"""Tests for container timeout handling — explicit docker stop on timeout.

Validates the Popen-based container execution pattern:
- ``subprocess.Popen(["docker", "run", ...])`` launches the container
- ``proc.wait(timeout=N)`` blocks until exit or timeout
- ``TimeoutExpired`` triggers ``_stop_container(name)`` then ``proc.wait(30)``
- ``KeyboardInterrupt`` triggers ``_stop_container(name)`` then ``SystemExit(130)``
- ``_stop_container`` calls ``subprocess.run(["docker", "stop", ...])``
- ``--rm`` and ``--name`` flags are present in docker run args
- Container names follow expected naming conventions
- Progress.jsonl and card artifacts are harvested even after timeout
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from silverquillm.cli import _stop_container, main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def cards_dir(tmp_path: Path) -> Path:
    """Minimal cards directory with a couple of SOS cards."""
    sos = tmp_path / "cards" / "sos"
    for cn in ("1", "2"):
        card_dir = sos / cn
        card_dir.mkdir(parents=True)
        (card_dir / "card_spec.json").write_text(
            json.dumps({
                "name": f"Card {cn}",
                "collector_number": cn,
                "set_code": "sos",
                "mana_cost": "{1}",
                "type_line": "Creature",
                "oracle_text": "Test",
                "complexity_tier": "T1",
            }),
            encoding="utf-8",
        )
        (card_dir / "card_impl.py").write_text(
            f'"""Card {cn} implementation."""\n\nclass Card{cn}:\n    pass\n',
            encoding="utf-8",
        )
    return tmp_path / "cards"


@pytest.fixture()
def engine_dir(tmp_path: Path) -> Path:
    eng = tmp_path / "engine"
    eng.mkdir(parents=True)
    (eng / "base.py").write_text("# engine base\n", encoding="utf-8")
    return eng


def _make_stage_mock(workspace: Path, output: Path):
    """Return a side_effect for stage_workspace that returns pre-made dirs."""
    def _stage(*args, **kwargs):
        workspace.mkdir(exist_ok=True)
        output.mkdir(exist_ok=True)
        return workspace, output
    return _stage


def _make_popen_mock(*, returncode=0, wait_side_effect=None):
    """Create a mock Popen object with configurable wait() behavior.

    Parameters
    ----------
    returncode : int
        The return code the mock process reports after wait().
    wait_side_effect : exception or None
        If set, ``proc.wait()`` will raise this on first call.
        After docker stop, a second ``proc.wait(timeout=30)`` should succeed.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = returncode

    if wait_side_effect is not None:
        # First wait() raises (timeout/interrupt), second wait() succeeds
        mock_proc.wait.side_effect = [wait_side_effect, None]
    else:
        mock_proc.wait.return_value = None

    return mock_proc


# ---------------------------------------------------------------------------
# _stop_container unit tests
# ---------------------------------------------------------------------------


class TestStopContainer:
    """Unit tests for the _stop_container helper."""

    @patch("silverquillm.cli.subprocess.run")
    def test_calls_docker_stop_with_correct_args(self, mock_run):
        """docker stop -t 10 <name> should be called."""
        mock_run.return_value = MagicMock(returncode=0)
        _stop_container("my-container")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "stop", "-t", "10", "my-container"]

    @patch("silverquillm.cli.subprocess.run")
    def test_grace_period_is_10_seconds(self, mock_run):
        """The -t flag should specify 10 seconds."""
        mock_run.return_value = MagicMock(returncode=0)
        _stop_container("test-ctr")

        cmd = mock_run.call_args[0][0]
        t_idx = cmd.index("-t")
        assert cmd[t_idx + 1] == "10"

    @patch("silverquillm.cli.subprocess.run")
    def test_swallows_errors(self, mock_run):
        """Errors from docker stop should be swallowed (container may already be gone)."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker stop")
        # Should not raise
        _stop_container("gone-container")

    @patch("silverquillm.cli.subprocess.run")
    def test_swallows_timeout(self, mock_run):
        """Even a timeout on docker stop itself should be swallowed."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker stop", 30)
        _stop_container("stuck-container")


# ---------------------------------------------------------------------------
# Run command — normal completion (Popen-based)
# ---------------------------------------------------------------------------


class TestRunNormalCompletion:
    """When the container exits normally, docker stop should NOT be called."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_no_docker_stop_on_success(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(returncode=0)
        mock_popen.return_value = mock_proc

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        # Popen should have been called once (docker run)
        mock_popen.assert_called_once()
        popen_cmd = mock_popen.call_args[0][0]
        assert popen_cmd[0] == "docker"
        assert popen_cmd[1] == "run"

        # proc.wait() should have been called with a timeout
        mock_proc.wait.assert_called_once()
        wait_kwargs = mock_proc.wait.call_args
        assert "timeout" in (wait_kwargs.kwargs if wait_kwargs.kwargs else {}) or \
               (wait_kwargs.args and isinstance(wait_kwargs.args[0], (int, float)))

        # subprocess.run should NOT have been called (no docker stop needed)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Run command — timeout triggers docker stop (Popen-based)
# ---------------------------------------------------------------------------


class TestRunTimeout:
    """When proc.wait() raises TimeoutExpired, docker stop must be called."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_stop_called_on_timeout(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 3600),
        )
        mock_popen.return_value = mock_proc

        # subprocess.run is used only for docker stop
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        # docker stop should have been called via subprocess.run
        mock_run.assert_called_once()
        stop_cmd = mock_run.call_args[0][0]
        assert stop_cmd[0] == "docker"
        assert stop_cmd[1] == "stop"

        # proc.wait() should have been called twice:
        # 1) initial wait with timeout (raises TimeoutExpired)
        # 2) wait after docker stop (cleanup, timeout=30)
        assert mock_proc.wait.call_count == 2

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_stop_uses_correct_container_name(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 3600),
        )
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        # Extract container name from Popen's docker run --name arg
        popen_cmd = mock_popen.call_args[0][0]
        name_idx = popen_cmd.index("--name")
        container_name = popen_cmd[name_idx + 1]

        # docker stop should use the same name
        stop_cmd = mock_run.call_args[0][0]
        assert stop_cmd[-1] == container_name

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_timeout_output_mentions_timeout(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 3600),
        )
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        combined = result.output.lower()
        assert "timed out" in combined or "timeout" in combined


# ---------------------------------------------------------------------------
# Run command — KeyboardInterrupt triggers docker stop (Popen-based)
# ---------------------------------------------------------------------------


class TestRunKeyboardInterrupt:
    """Ctrl+C should gracefully stop the container."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_stop_on_keyboard_interrupt(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock()
        mock_proc.wait.side_effect = KeyboardInterrupt()
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        # docker stop should have been called via subprocess.run
        mock_run.assert_called_once()
        stop_cmd = mock_run.call_args[0][0]
        assert stop_cmd[0:2] == ["docker", "stop"]

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_interrupt_exits_with_130(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        """KeyboardInterrupt should result in SystemExit(130)."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock()
        mock_proc.wait.side_effect = KeyboardInterrupt()
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        # Click captures SystemExit — check exit_code
        assert result.exit_code == 130

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_interrupt_message_mentions_interrupt(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock()
        mock_proc.wait.side_effect = KeyboardInterrupt()
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        combined = result.output.lower()
        assert "interrupt" in combined or "graceful" in combined


# ---------------------------------------------------------------------------
# Container name format (Popen-based)
# ---------------------------------------------------------------------------


class TestContainerName:
    """Container names should follow silverquillm-{run_name} format."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_run_container_name_format(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        """Run command container should be named silverquillm-{run_name}."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(returncode=0)
        mock_popen.return_value = mock_proc

        runner.invoke(
            main,
            ["run", "--image", "my-img:v1", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        popen_cmd = mock_popen.call_args[0][0]
        name_idx = popen_cmd.index("--name")
        container_name = popen_cmd[name_idx + 1]
        assert container_name.startswith("silverquillm-my-img_")

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    def test_smoke_container_name_format(self, mock_popen, mock_run, runner):
        """Smoke command container should be named silverquillm-smoke-{pid}."""
        mock_proc = _make_popen_mock(returncode=0)
        mock_popen.return_value = mock_proc

        runner.invoke(main, ["smoke", "--image", "test-img"])

        popen_cmd = mock_popen.call_args[0][0]
        name_idx = popen_cmd.index("--name")
        container_name = popen_cmd[name_idx + 1]
        assert container_name.startswith("silverquillm-smoke-")


# ---------------------------------------------------------------------------
# Docker args: --rm and --name (Popen-based)
# ---------------------------------------------------------------------------


class TestDockerFlags:
    """Docker run command should include --rm and --name flags."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_rm_flag_present_in_run(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(returncode=0)
        mock_popen.return_value = mock_proc

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        popen_cmd = mock_popen.call_args[0][0]
        assert "--rm" in popen_cmd

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    def test_rm_flag_present_in_smoke(self, mock_popen, mock_run, runner):
        mock_proc = _make_popen_mock(returncode=0)
        mock_popen.return_value = mock_proc

        runner.invoke(main, ["smoke", "--image", "test-img"])

        popen_cmd = mock_popen.call_args[0][0]
        assert "--rm" in popen_cmd

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_name_flag_present_in_run(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(returncode=0)
        mock_popen.return_value = mock_proc

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(tmp_path / "results")],
        )

        popen_cmd = mock_popen.call_args[0][0]
        assert "--name" in popen_cmd


# ---------------------------------------------------------------------------
# Smoke command timeout/interrupt → docker stop (Popen-based)
# ---------------------------------------------------------------------------


class TestSmokeTimeout:
    """Smoke command should also call docker stop on timeout/interrupt."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    def test_smoke_docker_stop_on_timeout(self, mock_popen, mock_run, runner):
        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 120),
        )
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["smoke", "--image", "test-img"])

        # docker stop called via subprocess.run
        mock_run.assert_called_once()
        stop_cmd = mock_run.call_args[0][0]
        assert stop_cmd[0:2] == ["docker", "stop"]
        assert stop_cmd[-1].startswith("silverquillm-smoke-")

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    def test_smoke_docker_stop_on_interrupt(self, mock_popen, mock_run, runner):
        mock_proc = _make_popen_mock()
        mock_proc.wait.side_effect = KeyboardInterrupt()
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["smoke", "--image", "test-img"])

        # docker stop called via subprocess.run
        mock_run.assert_called_once()
        stop_cmd = mock_run.call_args[0][0]
        assert stop_cmd[0:2] == ["docker", "stop"]


# ---------------------------------------------------------------------------
# Harvest after timeout — progress.jsonl preserved (Popen-based)
# ---------------------------------------------------------------------------


class TestHarvestAfterTimeout:
    """Progress.jsonl and other output artifacts should be harvested after timeout."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_progress_jsonl_harvested_after_timeout(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        results_dir = tmp_path / "results"
        workspace.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        (output / "progress.jsonl").write_text(
            '{"event": "card_start", "card": "1"}\n'
            '{"event": "card_done", "card": "1"}\n'
        )

        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 3600),
        )
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(results_dir)],
        )

        run_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]

        progress = run_dir / "progress.jsonl"
        assert progress.exists()
        lines = progress.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "card_start"

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_modified_card_impls_harvested_after_timeout(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        results_dir = tmp_path / "results"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        ws_card = workspace / "cards" / "sos" / "1"
        ws_card.mkdir(parents=True, exist_ok=True)
        (ws_card / "card_impl.py").write_text("# partially completed\n")

        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 3600),
        )
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(results_dir)],
        )

        run_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]

        harvested = run_dir / "cards" / "1" / "card_impl.py"
        assert harvested.exists()
        assert harvested.read_text() == "# partially completed\n"

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_timeout_cards_get_timeout_status(self, mock_stage, mock_popen, mock_run, runner, tmp_path, cards_dir):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        results_dir = tmp_path / "results"
        mock_stage.side_effect = _make_stage_mock(workspace, output)

        mock_proc = _make_popen_mock(
            wait_side_effect=subprocess.TimeoutExpired("docker run", 3600),
        )
        mock_popen.return_value = mock_proc
        mock_run.return_value = MagicMock(returncode=0)

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
             "--results-dir", str(results_dir)],
        )

        run_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        run_dir = run_dirs[0]

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses["1"] == "timeout"
        assert statuses["2"] == "timeout"
