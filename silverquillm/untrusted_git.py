"""Run git over a repository a candidate controlled without executing anything it configured.

Git runs programs named in repository config (``core.fsmonitor``, filter drivers,
hooks), and a candidate owns its workspace's ``.git/config``. So git never opens
that repository directly: a scratch git directory holds a host-written config,
copies of the candidate's HEAD, refs and index, and borrows its object store
read-only through ``objects/info/alternates``.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from silverquillm.safe_files import (
    TreeLimitExceeded,
    iter_regular_files,
    open_directory,
    read_regular_at,
)

MAX_METADATA_FILES = 10_000
MAX_METADATA_BYTES = 256 * 1024 * 1024

ENVIRONMENT = {
    "PATH": os.defpath,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
}
OVERRIDES = (
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.untrackedCache=false",
    "-c", "protocol.allow=never",
)  # fmt: skip


def environment(home: Path) -> dict[str, str]:
    """A git environment that reads no system, global, or inherited configuration."""
    return {**ENVIRONMENT, "HOME": str(home), "GIT_CEILING_DIRECTORIES": str(home)}


def _copy_metadata(source: int, scratch: Path) -> None:
    (scratch / "config").write_text("[core]\n\trepositoryformatversion = 0\n\tbare = false\n")
    for name in ("HEAD", "index", "packed-refs"):
        try:
            (scratch / name).write_bytes(read_regular_at(source, name, MAX_METADATA_BYTES))
        except FileNotFoundError:
            continue
    refs = os.open("refs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=source)
    try:
        for relative, content in iter_regular_files(
            refs,
            accept=lambda path: True,
            max_files=MAX_METADATA_FILES,
            max_bytes=MAX_METADATA_BYTES,
        ):
            target = scratch / "refs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    finally:
        os.close(refs)
    (scratch / "objects/info").mkdir(parents=True)


def status_paths(workspace: Path, *, timeout: float = 5) -> list[str] | None:
    """``git status --porcelain -z`` paths for ``workspace``, or ``None`` when unavailable."""
    workspace = Path(workspace)
    try:
        source = open_directory(workspace, (".git",))
    except OSError:
        return None
    try:
        objects = open_directory(workspace, (".git", "objects"))
        os.close(objects)
        with tempfile.TemporaryDirectory(prefix="sq-untrusted-git-") as scratch:
            git_dir = Path(scratch) / "git"
            git_dir.mkdir()
            _copy_metadata(source, git_dir)
            (git_dir / "objects/info/alternates").write_text(
                str(PurePosixPath(workspace.resolve(), ".git", "objects")) + "\n"
            )
            status = subprocess.run(
                [
                    "git", *OVERRIDES,
                    "--git-dir", str(git_dir), "--work-tree", str(workspace),
                    "status", "--porcelain", "-z", "--untracked-files=all",
                    "--ignore-submodules=all",
                ],
                cwd=workspace,
                env=environment(Path(scratch)),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )  # fmt: skip
    except (OSError, TreeLimitExceeded, subprocess.SubprocessError):
        return None
    finally:
        os.close(source)
    if status.returncode:
        return None
    return [path for path in status.stdout.split("\0") if path]
