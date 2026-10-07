"""Whether some process holds a lock file, observed without taking or creating any lock.

Probing with ``flock`` would itself hold the lock for an instant, and a recovery or runner
that tried its own non-blocking lock in that instant would refuse to start. The kernel's
lock table (``/proc/locks``) answers the same question without touching the file.
"""

from __future__ import annotations

import os
from pathlib import Path

PROC_LOCKS = Path("/proc/locks")


def held_locks(source: Path = PROC_LOCKS) -> frozenset[tuple[int, int, int]] | None:
    """``(major, minor, inode)`` of every file with a granted ``flock``; None when unknown."""
    try:
        text = source.read_text(errors="replace")
    except OSError:
        return None
    held = set()
    for line in text.splitlines():
        fields = line.split()
        # A waiter's line carries "->" after its ordinal; it holds nothing yet.
        if len(fields) < 6 or fields[1] != "FLOCK":
            continue
        try:
            major, minor, inode = fields[5].split(":")
            held.add((int(major, 16), int(minor, 16), int(inode)))
        except ValueError:
            continue
    return frozenset(held)


def lock_held(path: Path, held: frozenset[tuple[int, int, int]] | None) -> bool | None:
    """True or False for an existing lock file, None when the lock table is unavailable.

    A missing lock file was never locked, so it is not held.
    """
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    if held is None:
        return None
    return (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino) in held
