"""Fast-tier (1 Hz) telemetry — lightweight signals between snapshot intervals.

Monitors cheap signals without Git operations or full-workspace stat sweeps:
- Tails /output/progress.jsonl → emits [progress] events
- Tails /output/system.log → emits [system] events
- Stats mtime on known card/engine paths → emits [edit] events

Each channel writes to its own append-only file under the run directory.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# Channel → filename mapping for telemetry output files
CHANNEL_FILES = {
    "runner": "runner.log",
    "snapshot": "snapshot_telemetry.jsonl",
    "stdout": "docker_stdout.log",
    "stderr": "docker_stderr.log",
    "error": "runner_errors.log",
    "progress": "progress.jsonl",
    "edit": "fast_telemetry.jsonl",
    "system": "system.log",
}


@dataclass
class FastTelemetry:
    """1 Hz telemetry loop that monitors cheap signals alongside the snapshot loop.

    Parameters
    ----------
    output_dir : Path
        Container output directory (mounted as /output inside Docker).
    run_dir : Path
        Host-side run results directory where channel files are written.
    workspace_dir : Path
        Workspace directory to stat for mtime changes on card/engine files.
    on_event : callable, optional
        Optional callback invoked with (channel, message) for each event.
    """

    output_dir: Path
    run_dir: Path
    workspace_dir: Path
    on_event: Callable[[str, str], None] | None = None

    # Internal state
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _progress_pos: int = field(default=0, init=False)
    _system_pos: int = field(default=0, init=False)
    _mtimes: dict[str, float] = field(default_factory=dict, init=False)
    _bootstrap_emitted: bool = field(default=False, init=False)

    def start(self) -> None:
        """Start the fast telemetry loop in a background thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._progress_pos = 0
        self._system_pos = 0
        self._mtimes = {}
        self._bootstrap_emitted = False
        self._thread = threading.Thread(
            target=self._loop,
            name="fast-telemetry",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the fast telemetry loop to stop and wait for it to exit."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
            if not thread.is_alive():
                self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        """Main 1 Hz poll loop."""
        while not self._stop_event.is_set():
            try:
                self._poll_progress()
                self._poll_system_log()
                self._poll_mtimes()
            except Exception:
                pass  # Never crash the telemetry thread
            self._stop_event.wait(timeout=1.0)

    def _poll_progress(self) -> None:
        """Tail /output/progress.jsonl and emit [progress] events."""
        progress_path = self.output_dir / "progress.jsonl"
        new_lines = self._tail_file(progress_path, "_progress_pos")
        for line in new_lines:
            self._emit("progress", line)

    def _poll_system_log(self) -> None:
        """Tail /output/system.log and emit [system] events."""
        system_path = self.output_dir / "system.log"
        new_lines = self._tail_file(system_path, "_system_pos")
        for line in new_lines:
            self._emit("system", line)

    def _poll_mtimes(self) -> None:
        """Stat known card/engine paths and emit [edit] events on mtime changes."""
        is_first_pass = not self._bootstrap_emitted
        paths = self._get_watched_paths()
        for p in paths:
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            key = str(p)
            prev = self._mtimes.get(key)
            if prev is not None and mtime > prev:
                event_data = json.dumps({
                    "type": "edit",
                    "path": str(p.relative_to(self.workspace_dir)),
                    "mtime": mtime,
                    "ts": time.time(),
                })
                self._emit("edit", event_data)
            self._mtimes[key] = mtime

        if is_first_pass:
            from datetime import datetime, timezone
            bootstrap_data = json.dumps({
                "event": "bootstrap",
                "ts": datetime.now(timezone.utc).isoformat(),
                "files_seen": len(self._mtimes),
                "poll_interval_s": 1.0,
            })
            self._emit("edit", bootstrap_data)
            self._bootstrap_emitted = True

    def _get_watched_paths(self) -> list[Path]:
        """Return the small set of paths to stat for edit detection."""
        paths: list[Path] = []
        # cards/*/*/card_impl.py (handles cards/{fdn,sos}/{card_id}/card_impl.py)
        # Also check cards/*/card_impl.py for simpler layouts
        cards_dir = self.workspace_dir / "cards"
        if cards_dir.is_dir():
            for impl in cards_dir.glob("**/card_impl.py"):
                paths.append(impl)
        # engine/*.py
        engine_dir = self.workspace_dir / "engine"
        if engine_dir.is_dir():
            for py_file in engine_dir.glob("*.py"):
                paths.append(py_file)
        return paths

    def _tail_file(self, path: Path, pos_attr: str) -> list[str]:
        """Read new complete lines from a file since last position."""
        if not path.exists():
            return []
        try:
            size = path.stat().st_size
        except OSError:
            return []
        pos = getattr(self, pos_attr)
        if size <= pos:
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                data = f.read()
        except OSError:
            return []

        # Only emit complete lines (ending with \n)
        lines = data.split("\n")
        # If last element is not empty, it's an incomplete line — keep it for next poll
        if lines and lines[-1] != "":
            complete = lines[:-1]
            consumed = sum(len(l) + 1 for l in complete)  # +1 for each \n
        else:
            complete = lines[:-1]  # last element is empty string after final \n
            consumed = len(data)

        setattr(self, pos_attr, pos + consumed)
        return [l for l in complete if l]  # skip empty lines

    def _emit(self, channel: str, message: str) -> None:
        """Write event to the channel's file and invoke callback."""
        # Write to channel file in run_dir
        filename = CHANNEL_FILES.get(channel)
        if filename and self.run_dir.exists():
            out_path = self.run_dir / filename
            try:
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(message.rstrip("\n") + "\n")
                    f.flush()
            except OSError:
                pass

        # Invoke callback if set
        if self.on_event:
            try:
                self.on_event(channel, message)
            except Exception:
                pass
