"""Workspace-only snapshots and an explicit, tested grading-source decision."""

from __future__ import annotations

import ast
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

from silverquillm.queue_state import _write_atomically

from .definition import KarnError, canonical, digest, read_regular

IGNORED = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
MAX_FILE_BYTES = 32 * 1024 * 1024
GRADED_TREES = ("engine", "cards")
GRADED_FILES = ("test_utils.py",)


def _graded(path: Path) -> bool:
    return bool(path.parts) and (path.parts[0] in GRADED_TREES or str(path) in GRADED_FILES)


def _classify(size: int | None, mode: int) -> str | None:
    if stat.S_ISLNK(mode):
        return "symlink_excluded"
    if not stat.S_ISREG(mode):
        return "not_regular_file"
    if size is not None and size > MAX_FILE_BYTES:
        return "file_too_large"
    return None


def copy_workspace(source: Path, destination: Path) -> dict:
    """Copy regular files; exclusions are ``omissions``, unreadable graded sources ``errors``.

    Only ``errors`` disqualify a copy for grading: a symlinked virtualenv or a large data
    file the agent left behind must not demote its final work to an earlier snapshot.
    """
    source, destination = Path(source), Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    errors, omissions, rows = [], [], []

    def unavailable(path: Path) -> None:
        (errors if _graded(path) else omissions).append(
            {"path": str(path), "reason": "file_unavailable_during_copy"}
        )

    def walk_failed(error: OSError) -> None:
        # fwalk names only the entry, not its parent; directories are probed before descent,
        # so this is a race, and an unplaceable failure is treated as disqualifying.
        errors.append({"path": str(error.filename), "reason": "file_unavailable_during_copy"})

    for directory, names, filenames, directory_fd in os.fwalk(
        source, follow_symlinks=False, onerror=walk_failed
    ):
        relative = Path(directory).relative_to(source)
        target = destination / relative
        target.mkdir(parents=True, exist_ok=True)
        kept = []
        for name in names:
            if name in IGNORED:
                continue
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                omissions.append({"path": str(relative / name), "reason": "symlink_excluded"})
                continue
            try:
                os.close(
                    os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                )
                os.listdir(Path(directory) / name)
            except OSError:
                unavailable(relative / name)
                continue
            kept.append(name)
        names[:] = kept
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            path = relative / name
            try:
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                reason = _classify(info.st_size, info.st_mode)
                if reason is not None:
                    omissions.append({"path": str(path), "reason": reason})
                    continue
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    reason = _classify(info.st_size, info.st_mode)
                    content = b"" if reason else stream.read(MAX_FILE_BYTES + 1)
                if reason is None and len(content) > MAX_FILE_BYTES:
                    reason = "file_too_large"
                if reason is not None:
                    omissions.append({"path": str(path), "reason": reason})
                    continue
                (target / name).write_bytes(content)
                (target / name).chmod(stat.S_IMODE(info.st_mode) & 0o777)
                rows.append([str(path), digest(content)])
            except OSError:
                unavailable(path)
    return {
        "digest": digest(canonical(sorted(rows))),
        "files": len(rows),
        "errors": errors,
        "omissions": omissions,
    }


def engine_health(workspace: Path) -> dict:
    engine = workspace / "engine"
    if not engine.is_dir():
        return {"usable": False, "reason": "engine_directory_missing"}
    for path in engine.rglob("*.py"):
        try:
            ast.parse(path.read_bytes(), filename=str(path.relative_to(workspace)))
        except (SyntaxError, ValueError, OSError):
            return {
                "usable": False,
                "reason": "engine_source_invalid",
                "path": str(path.relative_to(workspace)),
            }
    with tempfile.TemporaryDirectory(prefix="sq-engine-probe-") as scratch:
        code = "import sys; sys.path.insert(0, sys.argv[1]); import engine.card, engine.game_state, engine.types"
        try:
            checked = subprocess.run(
                [sys.executable, "-I", "-c", code, str(workspace)],
                cwd=scratch,
                env={"PATH": os.defpath, "HOME": scratch},
                capture_output=True,
                timeout=20,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"usable": False, "reason": "engine_import_timeout"}
    return {
        "usable": checked.returncode == 0,
        "reason": None if checked.returncode == 0 else "engine_import_failed",
    }


class WorkspaceSnapshots:
    def __init__(
        self, workspace: Path, run_dir: Path, *, interval_seconds: float = 60, retain: int = 8
    ):
        if interval_seconds <= 0 or retain < 1:
            raise ValueError("snapshot_interval_and_retention_must_be_positive")
        self.workspace, self.run_dir = Path(workspace), Path(run_dir)
        self.interval, self.retain = interval_seconds, retain
        self.entries = []
        self.stop = threading.Event()
        self.thread = None

    def capture(self, kind: str) -> None:
        name = f"{len(self.entries):05d}"
        directory = self.run_dir / "snapshots" / name
        try:
            copied = copy_workspace(self.workspace, directory)
            entry = {
                "path": str(directory.relative_to(self.run_dir)),
                "kind": kind,
                "captured_at": datetime.now(UTC).isoformat(),
                "retained": True,
                **copied,
            }
        except OSError:
            entry = {
                "path": str(directory.relative_to(self.run_dir)),
                "kind": kind,
                "retained": False,
                "errors": [{"reason": "snapshot_copy_failed"}],
            }
        self.entries.append(entry)
        retained = [row for row in self.entries if row["retained"] and row["kind"] != "baseline"]
        for old in retained[: -self.retain]:
            shutil.rmtree(self.run_dir / old["path"])
            old["retained"] = False
        _write_atomically(
            self.run_dir / "snapshots.json",
            canonical(self.entries).decode() + "\n",
            prefix=".snapshots-",
        )

    def __enter__(self):
        self.capture("baseline")

        def periodic():
            while not self.stop.wait(self.interval):
                self.capture("periodic")

        self.thread = threading.Thread(target=periodic, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        if self.thread is not None:
            self.thread.join()

    def select(
        self, *, final_name: str = "workspace_final", manifest_name: str = "grading-source.json"
    ) -> dict:
        final = self.run_dir / final_name
        captured = copy_workspace(self.workspace, final)
        health = engine_health(final)
        selection = {
            "final": {"path": final_name, **captured, "engine_health": health},
            "selected": None,
            "fallback": False,
            "reason": None,
            "snapshots": self.entries,
        }
        if health["usable"] and not captured["errors"]:
            selection["selected"] = final_name
        else:
            selection["reason"] = health["reason"] or "final_workspace_copy_incomplete"
            for entry in reversed(self.entries):
                if not entry["retained"] or entry["errors"]:
                    continue
                checked = engine_health(self.run_dir / entry["path"])
                entry["engine_health"] = checked
                if checked["usable"]:
                    selection["selected"], selection["fallback"] = entry["path"], True
                    break
        _write_atomically(
            self.run_dir / manifest_name,
            canonical(selection).decode() + "\n",
            prefix=".grading-source-",
        )
        return selection


def retain_git_history(workspace: Path, run_dir: Path) -> dict:
    """Bundle referenced objects through a fresh repository that never reads workload config."""
    source = workspace / ".git"
    result = {"captured": False, "path": None, "reason": None, "commits": []}
    if source.is_symlink() or not source.is_dir():
        result["reason"] = "workspace_git_directory_unavailable"
        return result
    with tempfile.TemporaryDirectory(prefix="sq-git-evidence-") as scratch:
        safe = Path(scratch) / "repository.git"
        safe.mkdir()
        (safe / "objects").mkdir()
        (safe / "refs").mkdir()
        (safe / "config").write_text("[core]\nrepositoryformatversion = 0\nbare = true\n")
        try:
            objects = source / "objects"
            if objects.is_symlink():
                raise KarnError("git_objects_symlink")
            for directory in objects.iterdir():
                if directory.is_symlink() or not directory.is_dir():
                    continue
                if directory.name != "pack" and not re.fullmatch(r"[0-9a-f]{2}", directory.name):
                    continue
                destination = safe / "objects" / directory.name
                destination.mkdir()
                for path in directory.iterdir():
                    if directory.name == "pack":
                        accepted = re.fullmatch(r"pack-[0-9a-f]{40}\.(pack|idx|rev)", path.name)
                    else:
                        accepted = re.fullmatch(r"[0-9a-f]{38}", path.name)
                    if accepted:
                        (destination / path.name).write_bytes(
                            read_regular(path, limit=256 * 1024 * 1024)
                        )
            refs = source / "refs"
            if refs.is_symlink():
                raise KarnError("git_refs_symlink")
            for directory, names, files, descriptor in os.fwalk(refs, follow_symlinks=False):
                names[:] = [name for name in names if not (Path(directory) / name).is_symlink()]
                for name in files:
                    path = Path(directory) / name
                    relative = path.relative_to(source)
                    if relative.parts[1] not in ("heads", "tags"):
                        continue
                    value = read_regular(path, limit=256).decode().strip()
                    if not re.fullmatch(r"[0-9a-f]{40}", value):
                        raise KarnError("git_reference_invalid")
                    target = safe / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(value + "\n")
            packed = source / "packed-refs"
            if packed.exists():
                lines = []
                for line in read_regular(packed).decode().splitlines():
                    if re.fullmatch(r"[0-9a-f]{40} refs/(heads|tags)/[A-Za-z0-9_./-]+", line):
                        lines.append(line)
                (safe / "packed-refs").write_text("\n".join(lines) + "\n")
            head = read_regular(source / "HEAD", limit=256).decode().strip()
            if not re.fullmatch(r"(?:ref: refs/heads/[A-Za-z0-9_./-]+|[0-9a-f]{40})", head):
                raise KarnError("git_head_invalid")
            (safe / "HEAD").write_text(head + "\n")
            environment = {
                "PATH": os.defpath,
                "HOME": scratch,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
            }
            command = [
                "git",
                "--git-dir",
                str(safe),
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "core.fsmonitor=false",
            ]
            listed = subprocess.run(
                [*command, "rev-list", "--all"],
                env=environment,
                capture_output=True,
                check=False,
                timeout=15,
            )
            if listed.returncode or not listed.stdout.strip():
                result["reason"] = "no_referenced_git_commits"
            else:
                bundle = run_dir / "git-history.bundle"
                created = subprocess.run(
                    [*command, "bundle", "create", str(bundle), "--all"],
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=30,
                )
                if created.returncode:
                    result["reason"] = "git_bundle_unavailable"
                else:
                    result.update(
                        captured=True,
                        path="git-history.bundle",
                        commits=listed.stdout.decode().splitlines(),
                        digest=digest(bundle.read_bytes()),
                    )
        except (KarnError, OSError, ValueError, subprocess.TimeoutExpired):
            result["reason"] = "git_evidence_unavailable"
    (run_dir / "git-history.json").write_bytes(canonical(result) + b"\n")
    return result
