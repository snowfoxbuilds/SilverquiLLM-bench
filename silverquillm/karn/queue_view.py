"""Read-only rendering of Karn batches for `queue ls` and `top`."""

from __future__ import annotations

import os
import select
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from .batching import queue_rows

_ESC = "\x1b"


def render_rows(rows: list[dict]) -> list[str]:
    if not rows:
        return ["no batches"]
    lines = []
    for row in rows:
        if row["status"] == "unsupported_legacy_batch":
            lines.append(f"{row['batch']} [legacy]: unsupported legacy batch")
        elif row["status"] == "error":
            lines.append(f"{row['batch']} [{row['format']}]: error ({row['error']})")
        else:
            lines.append(
                f"{row['batch']} [{row['format']}]: {row['status']}"
                f" ({row.get('started', 0)}/{row.get('total', 0)})"
            )
    return lines


def _terminal_key_reader(interval: float) -> Callable[[], str | None]:
    fd = sys.stdin.fileno()

    def read_key() -> str | None:
        ready, _, _ = select.select([fd], [], [], interval)
        if not ready:
            return None
        return os.read(fd, 1).decode("utf-8", errors="replace")

    return read_key


def run_top(
    batches_dir: Path,
    *,
    interval: float = 2.0,
    out: TextIO | None = None,
    read_key: Callable[[], str | None] | None = None,
    max_frames: int | None = None,
) -> int:
    """Redraw the queue every *interval* seconds until ``q`` (or *max_frames*).

    Read-only: it never writes a batch file, a state file, or the lock. Without
    a terminal on stdin it draws a single frame, like ``queue ls``.
    """
    out = out or sys.stdout
    interactive = read_key is None and sys.stdin.isatty() and out.isatty()
    old_termios = None
    if interactive:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_termios = termios.tcgetattr(fd)
        tty.setraw(fd)
        out.write(f"{_ESC}[?1049h{_ESC}[?25l")
        read_key = _terminal_key_reader(interval)
    elif read_key is None:
        max_frames = 1 if max_frames is None else max_frames
        read_key = lambda: None  # noqa: E731

    stop = False

    def _stop(signum: int, frame: object) -> None:
        nonlocal stop
        stop = True

    old_handlers = {}
    if interactive:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, _stop)
    frames = 0
    try:
        while not stop:
            body = render_rows(queue_rows(batches_dir))
            header = f"silverquillm top — refresh {interval:g}s — q to quit"
            if interactive:
                out.write(f"{_ESC}[2J{_ESC}[H")
                out.write("\r\n".join([header, *body, ""]))
            else:
                out.write("\n".join([header, *body, ""]))
            out.flush()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
            if read_key() in ("q", "Q", "\x03"):
                break
    finally:
        if interactive:
            import termios

            out.write(f"{_ESC}[?25h{_ESC}[?1049l")
            out.flush()
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_termios)
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
    return frames
