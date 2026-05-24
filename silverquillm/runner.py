"""Container lifecycle management with pipe-reader + poll-loop architecture.

Two dedicated threads drain Docker stdout/stderr pipes to host files.
The main thread polls all files on a ~1s interval for live streaming,
timeout enforcement, and snapshot callbacks.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from silverquillm.card_names import resolve_card_names_in_line
from silverquillm.telemetry import FastTelemetry

# ANSI color helpers
_GRAY = "\033[90m"
_BLUE = "\033[34m"
_GREEN = "\033[32m"
_RESET = "\033[0m"

_SNAPSHOT_INTERVAL = 60  # seconds between snapshot callbacks


@dataclass
class LifecycleResult:
    exit_code: int | None
    timed_out: bool
    timeout_reason: str | None  # "hard_timeout" | "hang_timeout" | None
    container_name: str


class ContainerLifecycle:
    """Launch a Docker container, stream output, enforce timeouts, return result."""

    def __init__(
        self,
        image: str,
        container_name: str,
        workspace: Path,
        output: Path,
        hard_timeout: int,
        hang_timeout: int = 900,
        env_args: list[str] | None = None,
        snapshot_callback: callable | None = None,
        run_dir: Path | None = None,
        card_name_map: dict[str, str] | None = None,
    ):
        self.image = image
        self.container_name = container_name
        self.workspace = Path(workspace)
        self.output = Path(output)
        self.hard_timeout = hard_timeout
        self.hang_timeout = hang_timeout
        self.env_args = env_args or []
        self.snapshot_callback = snapshot_callback
        self.run_dir = Path(run_dir) if run_dir else None
        self.card_name_map = card_name_map or {}

        # Pipe drain target files — when run_dir is set, write directly there
        # (no .tmp intermediate); otherwise fall back to legacy .tmp in output/.
        if self.run_dir:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._stdout_path = self.run_dir / "docker_stdout.log"
            self._stderr_path = self.run_dir / "docker_stderr.log"
        else:
            self._stdout_path = self.output / "docker_stdout.tmp"
            self._stderr_path = self.output / "docker_stderr.tmp"

        # Monitored files (written by the container inside /output)
        self._system_log_path = self.output / "system.log"
        self._progress_path = self.output / "progress.jsonl"

        # File positions for incremental reads
        self._file_positions: dict[Path, int] = {}

    def run(self) -> LifecycleResult:
        """Launch container, stream output, enforce timeouts, return result."""
        self.output.mkdir(parents=True, exist_ok=True)

        cmd = [
            "docker", "run", "--rm", "--name", self.container_name,
            "--runtime", "runc", "--network=host",
            "-v", f"{self.workspace}:/workspace",
            "-v", f"{self.output}:/output",
            *self.env_args,
            self.image,
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Start pipe-reader threads
        stdout_thread = threading.Thread(
            target=self._drain_pipe,
            args=(proc.stdout, self._stdout_path),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._drain_pipe,
            args=(proc.stderr, self._stderr_path),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        # Start fast-tier (1 Hz) telemetry if run_dir is available
        fast_telemetry: FastTelemetry | None = None
        if self.run_dir:
            fast_telemetry = FastTelemetry(
                output_dir=self.output,
                run_dir=self.run_dir,
                workspace_dir=self.workspace,
            )
            fast_telemetry.start()

        # Initialize tracking state
        start = time.monotonic()
        last_activity = start
        last_snapshot = start
        self._file_positions = {}

        timeout_reason: str | None = None

        try:
            while True:
                # Check if process has exited
                ret = proc.poll()
                if ret is not None:
                    break

                # Read and print new data from all monitored files
                had_activity = self._read_and_print_new_bytes()
                if had_activity:
                    last_activity = time.monotonic()

                now = time.monotonic()

                # Hard timeout check
                if now - start > self.hard_timeout:
                    timeout_reason = "hard_timeout"
                    self._docker_stop()
                    break

                # Hang timeout check
                if now - last_activity > self.hang_timeout:
                    timeout_reason = "hang_timeout"
                    self._docker_stop()
                    break

                # Snapshot callback
                if self.snapshot_callback and now - last_snapshot >= _SNAPSHOT_INTERVAL:
                    self.snapshot_callback()
                    last_snapshot = now

                time.sleep(1)

        except KeyboardInterrupt:
            self._docker_stop()
            timeout_reason = None
        finally:
            # Stop fast-tier telemetry
            if fast_telemetry:
                fast_telemetry.stop()

        # Wait for pipe readers to finish
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)

        # Final read pass to flush any remaining data
        self._read_and_print_new_bytes()

        # NOTE: docker_stdout.log and docker_stderr.log are now streamed
        # directly to run_dir by _drain_pipe. The .tmp files in output/ are
        # kept for backward compat with _read_and_print_new_bytes but we no
        # longer copy them to .log here. See KEY_DECISIONS.md.

        # Get exit code (may need to wait briefly after docker stop)
        exit_code = proc.poll()
        if exit_code is None:
            try:
                exit_code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                exit_code = proc.wait()

        return LifecycleResult(
            exit_code=exit_code,
            timed_out=timeout_reason is not None,
            timeout_reason=timeout_reason,
            container_name=self.container_name,
        )

    def _drain_pipe(self, pipe, path: Path) -> None:
        """Dedicated thread: drain a subprocess pipe to a file on disk.

        Writes to *path* which is either the run_dir log (append, line-buffered,
        UTF-8 text) or the legacy .tmp file (binary) depending on how the runner
        was configured.

        Uses io.TextIOWrapper over the binary pipe for proper incremental UTF-8
        decoding — avoids corruption when multibyte characters span read boundaries.
        """
        import io as _io

        # Determine mode based on file suffix: .log → run_dir (text append),
        # .tmp → legacy (binary write).
        use_text_mode = path.suffix == ".log"

        if use_text_mode:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", buffering=1, encoding="utf-8", errors="replace") as f:
                text_stream = _io.TextIOWrapper(
                    pipe, encoding="utf-8", errors="replace"
                )
                for line in text_stream:
                    f.write(line)
        else:
            with open(path, "wb") as f:
                text_stream = _io.TextIOWrapper(
                    pipe, encoding="utf-8", errors="replace"
                )
                for line in text_stream:
                    raw = line.encode("utf-8")
                    f.write(raw)
                    f.flush()

    def _read_and_print_new_bytes(self) -> bool:
        """Read new bytes from each monitored file since last position.

        Returns True if any file had new data.
        """
        had_new = False

        files_and_labels = [
            (self._stdout_path, "", None),          # default color
            (self._stderr_path, "stderr", _GRAY),
            (self._system_log_path, "system", _BLUE),
            (self._progress_path, "progress", _GREEN),
        ]

        # Channels where card names should be resolved at print time
        _RESOLVE_NAME_LABELS = {"progress", "system"}

        for path, label, color in files_and_labels:
            if not path.exists():
                continue

            pos = self._file_positions.get(path, 0)
            try:
                size = path.stat().st_size
            except OSError:
                continue

            if size <= pos:
                continue

            try:
                with open(path, "rb") as f:
                    f.seek(pos)
                    data = f.read()
                    if data:
                        had_new = True
                        self._file_positions[path] = pos + len(data)
                        text = data.decode("utf-8", errors="replace")
                        if label and color:
                            for line in text.splitlines(keepends=True):
                                # Resolve card names for terminal display
                                if label in _RESOLVE_NAME_LABELS and self.card_name_map:
                                    line = resolve_card_names_in_line(line, self.card_name_map)
                                print(f"{color}[{label}]{_RESET} {line}", end="")
                        else:
                            print(text, end="")
            except OSError:
                continue

        return had_new

    def _docker_stop(self) -> None:
        """Gracefully stop the container."""
        subprocess.run(
            ["docker", "stop", "-t", "10", self.container_name],
            timeout=30,
            check=False,
        )
