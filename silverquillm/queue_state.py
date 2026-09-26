"""Runtime-independent queue locking and atomic state persistence."""

from __future__ import annotations

import fcntl
import json
import os
import socket
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

LOCK_FILENAME = ".scheduler.lock"


class SchedulerLockedError(Exception):
    """A scheduler already owns this queue."""


def _now():
    return datetime.now(UTC)


def _stamp(moment):
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_atomically(path: Path, payload: str, *, prefix: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=prefix, suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class LockStatus:
    """Whether a scheduler holds the lock right now, and what the lock file
    records about its holder (stale once the holder exits)."""

    held: bool
    holder: dict[str, Any] | None


def _read_holder(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class SchedulerLock:
    """``flock`` on ``batches/.scheduler.lock`` for the scheduler's lifetime."""

    def __init__(self, batches_dir: Path) -> None:
        self.batches_dir = Path(batches_dir)
        self.path = self.batches_dir / LOCK_FILENAME
        self._fd: int | None = None

    def __enter__(self) -> Self:
        self.batches_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            holder = _read_holder(self.path) or {}
            raise SchedulerLockedError(
                f"another scheduler holds {self.path}"
                + (
                    f" (pid {holder.get('pid')} on {holder.get('hostname')} since {holder.get('started_at')})"
                    if holder
                    else ""
                )
                + " — one scheduler per batches directory; refusing to start a second"
            ) from None
        holder = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "started_at": _stamp(_now()),
        }
        os.ftruncate(fd, 0)
        os.write(fd, (json.dumps(holder, sort_keys=True) + "\n").encode("utf-8"))
        self._fd = fd
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


def lock_status(batches_dir: Path) -> LockStatus:
    """Read-only probe: is the lock held?  Never takes the lock for longer
    than the probe, never writes the file."""
    path = Path(batches_dir) / LOCK_FILENAME
    if not path.exists():
        return LockStatus(held=False, holder=None)
    holder = _read_holder(path)
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return LockStatus(held=False, holder=holder)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return LockStatus(held=True, holder=holder)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return LockStatus(held=False, holder=holder)
    finally:
        os.close(fd)
