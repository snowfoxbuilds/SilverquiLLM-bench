"""Read trees a candidate controlled without following its links.

Every path component below a trusted root is opened relative to its parent's
descriptor with ``O_NOFOLLOW``, so swapping any directory for a symlink, even
while a live container still writes the tree, fails instead of redirecting a
read to host files.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath

DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class TreeLimitExceeded(OSError):
    """A copy would pass its file-count or byte cap."""


def open_directory(root: Path, parts: tuple[str, ...] = ()) -> int:
    """A descriptor for ``root/parts...`` in which no component may be a symlink."""
    descriptor = os.open(root, DIRECTORY_FLAGS)
    try:
        for part in parts:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def read_regular_at(directory: int, name: str, limit: int) -> bytes:
    """The bytes of a regular, singly linked file ``name`` in ``directory``, at most ``limit``."""
    descriptor = os.open(name, FILE_FLAGS, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OSError(f"not a regular file: {name}")
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise TreeLimitExceeded(f"file too large: {name}")
    return value


def iter_regular_files(
    directory: int,
    *,
    accept: Callable[[PurePosixPath], bool],
    max_files: int,
    max_bytes: int,
) -> Iterator[tuple[PurePosixPath, bytes]]:
    """Yield accepted regular files below ``directory``; links and special files are skipped."""
    budget = {"files": max_files, "bytes": max_bytes}

    def walk(descriptor: int, prefix: PurePosixPath):
        for name in sorted(os.listdir(descriptor)):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            relative = prefix / name
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, DIRECTORY_FLAGS, dir_fd=descriptor)
                try:
                    yield from walk(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and accept(relative):
                if budget["files"] == 0:
                    raise TreeLimitExceeded("too many files")
                content = read_regular_at(descriptor, name, budget["bytes"])
                budget["files"] -= 1
                budget["bytes"] -= len(content)
                yield relative, content

    yield from walk(directory, PurePosixPath())
