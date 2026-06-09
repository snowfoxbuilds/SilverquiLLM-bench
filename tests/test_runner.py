"""Tests for silverquillm.runner — ContainerLifecycle pipe-reader + poll-loop."""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from silverquillm.runner import ContainerLifecycle, LifecycleResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_popen(
    *,
    stdout_data: bytes = b"hello from container\n",
    stderr_data: bytes = b"",
    exit_code: int = 0,
    hang_after_bytes: bool = False,
    never_exit: bool = False,
    exit_delay: float = 0.0,
):
    """Build a mock Popen whose stdout/stderr behave like real pipes.

    Parameters
    ----------
    stdout_data : bytes written to the stdout pipe before EOF.
    stderr_data : bytes written to the stderr pipe before EOF.
    exit_code : process return code.
    hang_after_bytes : if True, stdout delivers data then blocks forever (no EOF).
    never_exit : if True, poll() never returns a non-None value until docker stop.
    exit_delay : seconds to wait before poll() starts returning exit_code.
    """
    import io

    mock_proc = MagicMock()

    # --- stdout pipe ---
    if hang_after_bytes:
        # Deliver initial data, then block on subsequent reads forever
        _first_read = [True]
        _stop_event = threading.Event()

        def _stdout_read(size=4096):
            if _first_read[0]:
                _first_read[0] = False
                return stdout_data
            # Block until the test stops us (simulates a hung container)
            _stop_event.wait(timeout=30)
            return b""

        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read = _stdout_read
        mock_proc._test_stop_event = _stop_event
    else:
        mock_proc.stdout = io.BytesIO(stdout_data)

    mock_proc.stderr = io.BytesIO(stderr_data)

    # --- poll / wait ---
    _start = time.monotonic()
    _stopped = threading.Event()

    def _poll():
        if never_exit and not _stopped.is_set():
            return None
        if exit_delay and (time.monotonic() - _start) < exit_delay:
            return None
        return exit_code

    mock_proc.poll = MagicMock(side_effect=_poll)
    mock_proc.wait = MagicMock(return_value=exit_code)
    mock_proc.kill = MagicMock()
    mock_proc._test_stopped = _stopped

    return mock_proc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# LifecycleResult dataclass
# ---------------------------------------------------------------------------


class TestLifecycleResult:
    """Verify the LifecycleResult dataclass fields exist and are usable."""

    def test_fields_present(self):
        r = LifecycleResult(exit_code=0, timed_out=False, timeout_reason=None, container_name="c")
        assert r.exit_code == 0
        assert r.timed_out is False
        assert r.timeout_reason is None
        assert r.container_name == "c"

    def test_timed_out_with_reason(self):
        r = LifecycleResult(exit_code=137, timed_out=True, timeout_reason="hard_timeout", container_name="x")
        assert r.timed_out is True
        assert r.timeout_reason == "hard_timeout"


# ---------------------------------------------------------------------------
# Normal exit
# ---------------------------------------------------------------------------


class TestNormalExit:
    """Mock process exits cleanly with code 0 after writing stdout data."""

    def test_exit_code_zero(self, workspace, output):
        mock_proc = _make_mock_popen(stdout_data=b"output line\n", exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="test-image",
                container_name="test-ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            result = lc.run()

        assert result.exit_code == 0
        assert result.timed_out is False
        assert result.timeout_reason is None
        assert result.container_name == "test-ctr"

    def test_non_zero_exit_code(self, workspace, output):
        mock_proc = _make_mock_popen(exit_code=1, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            result = lc.run()

        assert result.exit_code == 1
        assert result.timed_out is False

    def test_stdout_drained_to_file(self, workspace, output):
        """Pipe reader thread should write stdout data to docker_stdout.tmp."""
        mock_proc = _make_mock_popen(stdout_data=b"hello world\n", exit_code=0, exit_delay=0.2)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            lc.run()

        stdout_file = output / "docker_stdout.tmp"
        assert stdout_file.exists()
        assert b"hello world" in stdout_file.read_bytes()


# ---------------------------------------------------------------------------
# Hard timeout
# ---------------------------------------------------------------------------


class TestHardTimeout:
    """Process never exits within hard_timeout → docker stop called."""

    def test_hard_timeout_triggers_docker_stop(self, workspace, output):
        mock_proc = _make_mock_popen(never_exit=True, exit_code=137)

        def _docker_stop_side_effect(*args, **kwargs):
            # Unblock poll() after docker stop is called
            mock_proc._test_stopped.set()

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc) as _, \
             patch("silverquillm.runner.subprocess.run", side_effect=_docker_stop_side_effect) as mock_run, \
             patch("silverquillm.runner.time.sleep"):  # speed up poll loop
            # Use a tiny hard timeout so test is fast
            lc = ContainerLifecycle(
                image="img",
                container_name="hard-ctr",
                workspace=workspace,
                output=output,
                hard_timeout=0,  # immediate timeout
            )
            result = lc.run()

        assert result.timed_out is True
        assert result.timeout_reason == "hard_timeout"

        # docker stop must have been called with the container name
        mock_run.assert_called()
        stop_call_args = mock_run.call_args[0][0]
        assert "docker" in stop_call_args
        assert "stop" in stop_call_args
        assert "hard-ctr" in stop_call_args

    def test_hard_timeout_result_container_name(self, workspace, output):
        mock_proc = _make_mock_popen(never_exit=True, exit_code=137)

        def _docker_stop_side_effect(*args, **kwargs):
            mock_proc._test_stopped.set()

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run", side_effect=_docker_stop_side_effect), \
             patch("silverquillm.runner.time.sleep"):
            lc = ContainerLifecycle(
                image="img",
                container_name="my-container",
                workspace=workspace,
                output=output,
                hard_timeout=0,
            )
            result = lc.run()

        assert result.container_name == "my-container"


# ---------------------------------------------------------------------------
# Hang timeout
# ---------------------------------------------------------------------------


class TestHangTimeout:
    """Process writes data then goes silent → hang timeout triggers docker stop."""

    def test_hang_timeout_triggers_docker_stop(self, workspace, output):
        mock_proc = _make_mock_popen(
            stdout_data=b"initial data\n",
            hang_after_bytes=True,
            never_exit=True,
            exit_code=137,
        )

        def _docker_stop_side_effect(*args, **kwargs):
            mock_proc._test_stopped.set()
            if hasattr(mock_proc, '_test_stop_event'):
                mock_proc._test_stop_event.set()

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run", side_effect=_docker_stop_side_effect) as mock_run, \
             patch("silverquillm.runner.time.sleep"):
            lc = ContainerLifecycle(
                image="img",
                container_name="hang-ctr",
                workspace=workspace,
                output=output,
                hard_timeout=9999,  # large so hard timeout doesn't fire
                hang_timeout=0,    # immediate hang timeout
            )
            result = lc.run()

        assert result.timed_out is True
        assert result.timeout_reason == "hang_timeout"

        mock_run.assert_called()
        stop_call_args = mock_run.call_args[0][0]
        assert "docker" in stop_call_args
        assert "stop" in stop_call_args
        assert "hang-ctr" in stop_call_args


# ---------------------------------------------------------------------------
# KeyboardInterrupt
# ---------------------------------------------------------------------------


class TestKeyboardInterrupt:
    """KeyboardInterrupt during poll loop → docker stop called, threads joined."""

    def test_keyboard_interrupt_calls_docker_stop(self, workspace, output):
        mock_proc = _make_mock_popen(never_exit=True, exit_code=130)
        call_count = [0]

        def _docker_stop_side_effect(*args, **kwargs):
            mock_proc._test_stopped.set()

        def _interrupt_on_sleep(seconds):
            call_count[0] += 1
            if call_count[0] >= 1:
                raise KeyboardInterrupt

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run", side_effect=_docker_stop_side_effect) as mock_run, \
             patch("silverquillm.runner.time.sleep", side_effect=_interrupt_on_sleep):
            lc = ContainerLifecycle(
                image="img",
                container_name="int-ctr",
                workspace=workspace,
                output=output,
                hard_timeout=9999,
            )
            result = lc.run()

        # docker stop should have been called
        mock_run.assert_called()
        stop_call_args = mock_run.call_args[0][0]
        assert "docker" in stop_call_args
        assert "stop" in stop_call_args
        assert "int-ctr" in stop_call_args

    def test_keyboard_interrupt_result_not_timed_out(self, workspace, output):
        """KeyboardInterrupt is a user cancellation, not a timeout."""
        mock_proc = _make_mock_popen(never_exit=True, exit_code=130)

        def _docker_stop_side_effect(*args, **kwargs):
            mock_proc._test_stopped.set()

        def _interrupt_on_sleep(seconds):
            raise KeyboardInterrupt

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run", side_effect=_docker_stop_side_effect), \
             patch("silverquillm.runner.time.sleep", side_effect=_interrupt_on_sleep):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=9999,
            )
            result = lc.run()

        # Implementation sets timeout_reason=None on KeyboardInterrupt
        assert result.timeout_reason is None


# ---------------------------------------------------------------------------
# Pipe reader threads
# ---------------------------------------------------------------------------


class TestPipeReaderThreads:
    """Verify pipe reader threads are started and joined."""

    def test_threads_are_started_and_joined(self, workspace, output):
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"), \
             patch("silverquillm.runner.threading.Thread") as MockThread:
            mock_t1 = MagicMock()
            mock_t2 = MagicMock()
            MockThread.side_effect = [mock_t1, mock_t2]

            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            lc.run()

        # Two threads created (stdout + stderr)
        assert MockThread.call_count == 2

        # Both started
        mock_t1.start.assert_called_once()
        mock_t2.start.assert_called_once()

        # Both joined
        mock_t1.join.assert_called_once()
        mock_t2.join.assert_called_once()


# ---------------------------------------------------------------------------
# Constructor / init
# ---------------------------------------------------------------------------


class TestContainerLifecycleInit:
    """Verify constructor accepts the documented parameters."""

    def test_required_params(self, workspace, output):
        lc = ContainerLifecycle(
            image="my-image",
            container_name="my-ctr",
            workspace=workspace,
            output=output,
            hard_timeout=600,
        )
        assert lc.image == "my-image"
        assert lc.container_name == "my-ctr"
        assert lc.hard_timeout == 600

    def test_default_hang_timeout(self, workspace, output):
        lc = ContainerLifecycle(
            image="img",
            container_name="ctr",
            workspace=workspace,
            output=output,
            hard_timeout=600,
        )
        assert lc.hang_timeout == 900

    def test_custom_hang_timeout(self, workspace, output):
        lc = ContainerLifecycle(
            image="img",
            container_name="ctr",
            workspace=workspace,
            output=output,
            hard_timeout=600,
            hang_timeout=120,
        )
        assert lc.hang_timeout == 120

    def test_env_args_default_none(self, workspace, output):
        lc = ContainerLifecycle(
            image="img",
            container_name="ctr",
            workspace=workspace,
            output=output,
            hard_timeout=600,
        )
        assert lc.env_args == []

    def test_snapshot_callback_accepted(self, workspace, output):
        cb = MagicMock()
        lc = ContainerLifecycle(
            image="img",
            container_name="ctr",
            workspace=workspace,
            output=output,
            hard_timeout=600,
            snapshot_callback=cb,
        )
        assert lc.snapshot_callback is cb


# ---------------------------------------------------------------------------
# Docker command construction
# ---------------------------------------------------------------------------


class TestDockerCommand:
    """Verify the docker run command is constructed correctly."""

    def test_docker_run_command_includes_image_and_name(self, workspace, output):
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="test-image:latest",
                container_name="my-ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            lc.run()

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "test-image:latest" in cmd
        assert "my-ctr" in cmd

    def test_popen_uses_pipe_for_stdout_stderr(self, workspace, output):
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            lc.run()

        kwargs = mock_popen.call_args[1]
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE

    def test_env_args_included_in_command(self, workspace, output):
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                env_args=["-e", "FOO=bar", "-e", "BAZ=qux"],
            )
            lc.run()

        cmd = mock_popen.call_args[0][0]
        assert "-e" in cmd
        assert "FOO=bar" in cmd
        assert "BAZ=qux" in cmd

    def test_default_resource_limits_in_command(self, workspace, output):
        """Containers are capped at 2 CPUs and 16g memory by default."""
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
            )
            lc.run()

        cmd = mock_popen.call_args[0][0]
        assert cmd[cmd.index("--cpus") + 1] == "2"
        assert cmd[cmd.index("--memory") + 1] == "16g"

    def test_resource_limits_are_overridable(self, workspace, output):
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                cpus="4",
                memory="32g",
            )
            lc.run()

        cmd = mock_popen.call_args[0][0]
        assert cmd[cmd.index("--cpus") + 1] == "4"
        assert cmd[cmd.index("--memory") + 1] == "32g"


# ---------------------------------------------------------------------------
# Snapshot callback
# ---------------------------------------------------------------------------


class TestSnapshotCallback:
    """Snapshot callback should be invoked periodically."""

    def test_snapshot_callback_called_at_least_once(self, workspace, output):
        """With _SNAPSHOT_INTERVAL=0 and a delayed exit, callback fires at least once."""
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.3)
        callback = MagicMock()

        # Patch _SNAPSHOT_INTERVAL to 0 so it fires on every poll iteration
        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"), \
             patch("silverquillm.runner._SNAPSHOT_INTERVAL", 0):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                snapshot_callback=callback,
            )
            lc.run()

        # With interval=0 and ~0.3s of polling, callback must fire at least once
        assert callback.call_count >= 1, (
            f"Expected snapshot callback to fire at least once, got {callback.call_count}"
        )

    def test_no_callback_when_none(self, workspace, output):
        """When snapshot_callback is None, no error occurs."""
        mock_proc = _make_mock_popen(exit_code=0, exit_delay=0.1)

        with patch("silverquillm.runner.subprocess.Popen", return_value=mock_proc), \
             patch("silverquillm.runner.subprocess.run"):
            lc = ContainerLifecycle(
                image="img",
                container_name="ctr",
                workspace=workspace,
                output=output,
                hard_timeout=300,
                snapshot_callback=None,
            )
            result = lc.run()

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Direct streaming to run_dir (no .tmp → .log copy)
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    rd = tmp_path / "run_dir"
    rd.mkdir()
    return rd


class TestDirectStreamToRunDir:
    """When run_dir is provided, logs stream directly there — no post-exit copy."""

    def test_stdout_written_to_run_dir_directly(self, workspace, output, run_dir):
        """docker_stdout.log appears in run_dir via direct streaming, not copy."""
        mock_proc = _make_mock_popen(stdout_data=b"stdout data\n", exit_code=0, exit_delay=0.1)

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

        run_dir_log = run_dir / "docker_stdout.log"
        assert run_dir_log.exists(), "docker_stdout.log should be streamed to run_dir"
        assert "stdout data" in run_dir_log.read_text(encoding="utf-8")

    def test_stderr_written_to_run_dir_directly(self, workspace, output, run_dir):
        """docker_stderr.log appears in run_dir via direct streaming."""
        mock_proc = _make_mock_popen(
            stdout_data=b"out\n", stderr_data=b"err data\n",
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

        run_dir_log = run_dir / "docker_stderr.log"
        assert run_dir_log.exists(), "docker_stderr.log should be streamed to run_dir"
        assert "err data" in run_dir_log.read_text(encoding="utf-8")

    def test_no_post_exit_copy_to_output_log(self, workspace, output, run_dir):
        """When run_dir is provided, output/docker_stdout.log is NOT created via copy."""
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

        # The .log file should NOT be created in output/ via shutil.copy2
        assert not (output / "docker_stdout.log").exists(), \
            "output/docker_stdout.log should not be created when run_dir is set"
        assert not (output / "docker_stderr.log").exists(), \
            "output/docker_stderr.log should not be created when run_dir is set"

    def test_no_tmp_files_when_run_dir_provided(self, workspace, output, run_dir):
        """When run_dir is provided, .tmp intermediates are not created."""
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

    def test_run_dir_log_content_matches_container_output(self, workspace, output, run_dir):
        """All container output lines appear in the run_dir log file."""
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
