"""Helpers for tests that fake ``os`` calls made relative to a directory
descriptor (``dir_fd``), as :mod:`silverquillm.created_directories` makes
them: a fake must recognise the entry it is aimed at whether the call names it
by path or by name-under-descriptor."""

from __future__ import annotations

import os
from pathlib import Path


def names(path: object, dir_fd: int | None, target: Path) -> bool:
    """Whether an ``os`` call's (*path*, *dir_fd*) pair names *target*: the
    path itself when no directory descriptor is given, else *target*'s own
    name resolved against a descriptor open on *target*'s parent."""
    if dir_fd is None:
        return Path(os.fsdecode(path)) == target  # type: ignore[arg-type]
    try:
        return Path(os.fsdecode(path)).name == target.name and os.path.samestat(  # type: ignore[arg-type]
            os.fstat(dir_fd), os.stat(target.parent)
        )
    except OSError:
        return False


def is_open_on(fd: int, path: Path) -> bool:
    """Whether *fd* is open on the very file *path* names right now."""
    try:
        here, there = os.fstat(fd), os.stat(path)
    except OSError:
        return False
    return os.path.samestat(here, there)
