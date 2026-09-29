"""Graded workspaces in the results repository, as binary diffs from one shared baseline.

Every run of a benchmark input starts from the same staged workspace, so the results
repository stores that baseline once, as a git bundle under ``baselines/``, and each run's
graded workspace as the diff from it under ``workspaces/<candidate-hash>/<run-id>/``
(see ADR-015). Both are write-once. The archived tree is exactly the copy grading used:
its content digest is the one the record's ``grading_source`` states, and every read
rebuilds the tree and refuses it unless both the git tree id and that digest match.

Trees are built with plumbing (``hash-object --no-filters``, ``update-index``) and
materialized with ``cat-file``, so no ``.gitattributes``, ignore rule, filter or user
configuration inside a workspace or on the host can change a byte. All git work happens in
a scratch repository; a run's own ``.git`` is never read or written.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from .definition import KarnError, canonical, digest, read_regular, strict_json
from .snapshots import IGNORED

FORMAT_VERSION = 1
BASELINES = "baselines"
WORKSPACES = "workspaces"
PATCH = "workspace.patch"
METADATA = "workspace.json"
MAX_PATCH_BYTES = 16 * 1024 * 1024
LOCK_SECONDS = 120
BASELINE_REF = "refs/baselines/base"
# What grading's workspace copy leaves out, so an archive holds nothing grading did not see.
GRADING_COPY_OMITS = sorted(IGNORED) + ["*.pyc", "symlinks", "non-regular files"]
OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")
# A fixed identity and date make the baseline commit id a function of its tree alone.
FIXED_COMMIT = {
    "GIT_AUTHOR_NAME": "SilverquiLLM Bench",
    "GIT_AUTHOR_EMAIL": "benchmark@example.invalid",
    "GIT_AUTHOR_DATE": "1970-01-01T00:00:00+0000",
    "GIT_COMMITTER_NAME": "SilverquiLLM Bench",
    "GIT_COMMITTER_EMAIL": "benchmark@example.invalid",
    "GIT_COMMITTER_DATE": "1970-01-01T00:00:00+0000",
}


class ArchiveRefused(KarnError):
    """This run's workspace cannot be archived or rebuilt; the reason is a stable code."""


def _files(directory: Path):
    """Regular files as grading's workspace copy keeps them, by relative POSIX path."""
    for root, names, filenames in os.walk(directory):
        names[:] = sorted(
            name
            for name in names
            if name not in IGNORED and not os.path.islink(os.path.join(root, name))
        )
        for name in sorted(filenames):
            path = Path(root) / name
            if name.endswith(".pyc") or not stat.S_ISREG(path.lstat().st_mode):
                continue
            yield path.relative_to(directory).as_posix(), path


def content_digest(directory: Path) -> str:
    """The digest grading's workspace copy records for the same files (``copy_workspace``)."""
    rows = [[relative, digest(path.read_bytes())] for relative, path in _files(Path(directory))]
    return digest(canonical(sorted(rows)))


class Scratch:
    """A throwaway bare repository whose git never reads host, user or workspace config."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.git_dir = self.root / "repository.git"
        self.environment = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(self.root),
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_ATTR_NOSYSTEM": "1",
            **FIXED_COMMIT,
        }
        self.git("init", "--bare", "--quiet", "--template=", str(self.git_dir), bare=True)
        self.indexes = 0

    def git(self, *arguments, stdin: bytes | None = None, index: Path | None = None, bare=False):
        command = ["git"]
        if not bare:
            command += ["--git-dir", str(self.git_dir)]
        command += [
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.attributesFile=/dev/null",
            *arguments,
        ]
        environment = dict(self.environment)
        if index is not None:
            environment["GIT_INDEX_FILE"] = str(index)
        result = subprocess.run(
            command,
            input=stdin,
            env=environment,
            cwd=self.root,
            capture_output=True,
            check=False,
            timeout=300,
        )
        if result.returncode:
            raise ArchiveRefused("git_failed:" + arguments[0])
        return result.stdout

    def index(self) -> Path:
        self.indexes += 1
        return self.root / f"index-{self.indexes}"

    def tree(self, directory: Path) -> str:
        """The git tree of *directory*'s kept files, content stored byte for byte."""
        files = list(_files(Path(directory)))
        paths = b"".join(str(path).encode() + b"\n" for _, path in files)
        if any(b"\n" in str(path).encode() for _, path in files):
            raise ArchiveRefused("workspace_path_not_representable")
        objects = self.git("hash-object", "-w", "--no-filters", "--stdin-paths", stdin=paths)
        ids = objects.decode().split()
        entries = b"".join(
            f"{'100755' if path.stat().st_mode & 0o111 else '100644'} {object_id}\t".encode()
            + relative.encode()
            + b"\0"
            for (relative, path), object_id in zip(files, ids, strict=True)
        )
        index = self.index()
        self.git("update-index", "-z", "--index-info", stdin=entries, index=index)
        return self.git("write-tree", index=index).decode().strip()

    def write_tree(self, tree: str, destination: Path) -> None:
        """Write every blob of *tree* under *destination*, with no checkout conversion."""
        listing = self.git("ls-tree", "-r", "-z", "--full-tree", tree)
        rows = []
        for entry in filter(None, listing.split(b"\0")):
            header, _, name = entry.partition(b"\t")
            mode, kind, object_id = header.decode().split()
            relative = PurePosixPath(name.decode())
            if (
                kind != "blob"
                or mode not in ("100644", "100755")
                or relative.is_absolute()
                or ".." in relative.parts
            ):
                raise ArchiveRefused("workspace_tree_entry_unsupported")
            rows.append((mode, object_id, relative))
        batch = self.git(
            "cat-file", "--batch", stdin=b"".join(row[1].encode() + b"\n" for row in rows)
        )
        offset = 0
        destination.mkdir(parents=True, exist_ok=True)
        for mode, object_id, relative in rows:
            end = batch.index(b"\n", offset)
            found, kind, size = batch[offset:end].decode().split()
            if found != object_id or kind != "blob":
                raise ArchiveRefused("workspace_blob_unavailable")
            start = end + 1
            path = destination.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(batch[start : start + int(size)])
            path.chmod(0o755 if mode == "100755" else 0o644)
            offset = start + int(size) + 1

    def baseline_commit(self, tree: str) -> str:
        commit = self.git("commit-tree", tree, "-m", "Benchmark workspace baseline")
        commit = commit.decode().strip()
        self.git("update-ref", BASELINE_REF, commit)
        return commit

    def bundle(self, path: Path) -> None:
        self.git("bundle", "create", "--quiet", str(path), BASELINE_REF)

    def unbundle(self, path: Path, tree: str) -> str:
        """Import a baseline bundle and return its commit, refusing any other tree."""
        heads = self.git("bundle", "unbundle", str(path)).decode().split()
        if len(heads) != 2 or heads[1] != BASELINE_REF or not OBJECT_ID.fullmatch(heads[0]):
            raise ArchiveRefused("baseline_bundle_invalid")
        if self.git("rev-parse", heads[0] + "^{tree}").decode().strip() != tree:
            raise ArchiveRefused("baseline_bundle_tree_mismatch")
        return heads[0]

    def diff(self, base: str, final: str) -> bytes:
        return self.git(
            "diff",
            "--binary",
            "--full-index",
            "--no-renames",
            "--no-color",
            "--no-textconv",
            "--no-ext-diff",
            base,
            final,
        )

    def apply(self, base: str, patch: Path) -> str:
        index = self.index()
        self.git("read-tree", base, index=index)
        if patch.stat().st_size:
            self.git(
                "apply", "--cached", "--binary", "--whitespace=nowarn", str(patch), index=index
            )
        return self.git("write-tree", index=index).decode().strip()


def graded_path(record, results_dir: Path) -> Path:
    """The graded copy named by the record, inside its run artifacts under *results_dir*.

    Artifact pointers are never followed: a record may come from another host, and its
    paths must never choose what is read.
    """
    selected = (record.run_metadata.get("grading_source") or {}).get("selected")
    if not isinstance(selected, str) or not selected:
        raise ArchiveRefused("no_graded_workspace")
    run_id = record.run_metadata.get("execution_run_id", record.run_id)
    relative = PurePosixPath(selected)
    if (
        not isinstance(run_id, str)
        or not RUN_ID.fullmatch(run_id)
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise ArchiveRefused("grading_source_invalid")
    directory = Path(results_dir).resolve() / run_id
    workspace = directory / relative
    if not workspace.is_dir():
        raise ArchiveRefused("workspace_unavailable")
    if not workspace.resolve().is_relative_to(directory):
        raise ArchiveRefused("grading_source_invalid")
    return workspace.resolve()


def graded_digest(record) -> str:
    """The content digest the record states for the tree grading used."""
    selection = record.run_metadata.get("grading_source") or {}
    selected = selection.get("selected")
    final = selection.get("final") or {}
    if selected == final.get("path"):
        value = final.get("digest")
    else:
        value = next(
            (
                e.get("digest")
                for e in selection.get("snapshots") or []
                if e.get("path") == selected
            ),
            None,
        )
    if not isinstance(value, str):
        raise ArchiveRefused("graded_digest_unrecorded")
    return value


def _baseline_snapshot(record, run_dir: Path) -> Path:
    """The run's baseline snapshot, which must hold exactly the staged benchmark workspace."""
    selection = record.run_metadata.get("grading_source") or {}
    entry = next(
        (
            e
            for e in selection.get("snapshots") or []
            if e.get("kind") == "baseline" and e.get("retained") and not e.get("errors")
        ),
        None,
    )
    relative = PurePosixPath(str((entry or {}).get("path")))
    if entry is None or relative.is_absolute() or ".." in relative.parts:
        raise ArchiveRefused("baseline_snapshot_unavailable")
    directory = run_dir / relative
    if not directory.is_dir() or not directory.resolve().is_relative_to(run_dir.resolve()):
        raise ArchiveRefused("baseline_snapshot_unavailable")
    staged = record.run_metadata["benchmark_input"].get("workspace_digest")
    if staged is None or content_digest(directory) != staged:
        raise ArchiveRefused("baseline_snapshot_mismatch")
    return directory


def archive_dir(results_repo: Path, candidate_hash: str, run_id: str) -> Path:
    if not CANDIDATE_HASH.fullmatch(candidate_hash) or not RUN_ID.fullmatch(run_id):
        raise ArchiveRefused("archive_identity_invalid")
    return Path(results_repo) / WORKSPACES / candidate_hash / run_id


def baseline_path(results_repo: Path, tree: str) -> Path:
    if not OBJECT_ID.fullmatch(tree):
        raise ArchiveRefused("baseline_tree_invalid")
    return Path(results_repo) / BASELINES / f"{tree}.bundle"


def read_metadata(directory: Path) -> dict:
    try:
        value = strict_json(read_regular(directory / METADATA))
    except KarnError:
        raise ArchiveRefused("workspace_metadata_invalid") from None
    fields = {"format_version", "run_id", "candidate_hash", "baseline", "graded", "patch"}
    if (
        not isinstance(value, dict)
        or not fields <= value.keys()
        or value["format_version"] != FORMAT_VERSION
        or not isinstance(value["baseline"], dict)
        or not isinstance(value["graded"], dict)
        or not isinstance(value["patch"], dict)
        or not OBJECT_ID.fullmatch(str(value["baseline"].get("tree")))
        or not OBJECT_ID.fullmatch(str(value["graded"].get("tree")))
        or not isinstance(value["graded"].get("content_digest"), str)
        or not isinstance(value["patch"].get("sha256"), str)
    ):
        raise ArchiveRefused("workspace_metadata_invalid")
    return value


def _rebuild(scratch: Scratch, bundle: Path, patch: Path, metadata: dict, destination: Path):
    base = metadata["baseline"]["tree"]
    scratch.unbundle(bundle, base)
    if digest(patch.read_bytes()) != metadata["patch"]["sha256"]:
        raise ArchiveRefused("workspace_patch_digest_mismatch")
    if scratch.apply(base, patch) != metadata["graded"]["tree"]:
        raise ArchiveRefused("workspace_tree_mismatch")
    scratch.write_tree(metadata["graded"]["tree"], destination)
    if content_digest(destination) != metadata["graded"]["content_digest"]:
        raise ArchiveRefused("workspace_content_mismatch")


def materialize(results_repo: Path, record, destination: Path) -> Path:
    """Rebuild the record's graded workspace from the results repository into *destination*.

    Refused unless the rebuilt tree is the archived tree and its content digest is the one
    the record itself states grading used.
    """
    directory = archive_dir(results_repo, record.candidate.hash, record.run_id)
    if not (directory / METADATA).is_file():
        raise ArchiveRefused("workspace_not_archived")
    metadata = read_metadata(directory)
    if (
        metadata["run_id"] != record.run_id
        or metadata["candidate_hash"] != record.candidate.hash
        or metadata["graded"]["content_digest"] != graded_digest(record)
    ):
        raise ArchiveRefused("workspace_archive_does_not_match_record")
    destination = Path(destination)
    if destination.exists():
        raise ArchiveRefused("materialize_destination_exists")
    with tempfile.TemporaryDirectory(prefix="sq-workspace-") as scratch_root:
        scratch = Scratch(Path(scratch_root))
        _rebuild(
            scratch,
            baseline_path(results_repo, metadata["baseline"]["tree"]),
            directory / PATCH,
            metadata,
            destination,
        )
    return destination


@contextlib.contextmanager
def _lock(results_repo: Path):
    directory = Path(results_repo) / WORKSPACES
    directory.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        deadline = time.monotonic() + LOCK_SECONDS
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ArchiveRefused("workspace_archive_locked") from None
                time.sleep(0.1)
        yield
    finally:
        os.close(descriptor)


def archive_run(results_repo: Path, record, run_dir: Path, *, dry_run: bool = False) -> dict:
    """Archive the record's graded workspace, verifying a full rebuild before anything is written.

    Returns ``{"status": "archived" | "exists" | "would_archive", ...}``; raises
    :class:`ArchiveRefused` when the run cannot be archived faithfully.
    """
    results_repo, run_dir = Path(results_repo), Path(run_dir)
    target = archive_dir(results_repo, record.candidate.hash, record.run_id)
    if (target / METADATA).is_file():
        return {"status": "exists", "path": str(target.relative_to(results_repo))}
    graded = graded_path(record, run_dir.parent)
    recorded = graded_digest(record)
    if content_digest(graded) != recorded:
        raise ArchiveRefused("graded_workspace_changed")
    baseline = _baseline_snapshot(record, run_dir)
    with tempfile.TemporaryDirectory(prefix="sq-archive-") as scratch_root:
        scratch_root = Path(scratch_root)
        writer = Scratch(scratch_root / "writer")
        base_tree, final_tree = writer.tree(baseline), writer.tree(graded)
        commit = writer.baseline_commit(base_tree)
        patch = scratch_root / PATCH
        patch.write_bytes(writer.diff(base_tree, final_tree))
        if patch.stat().st_size > MAX_PATCH_BYTES:
            raise ArchiveRefused("workspace_patch_too_large")
        bundle = scratch_root / "baseline.bundle"
        writer.bundle(bundle)
        changed = writer.git("diff", "--name-only", "-z", "--no-renames", base_tree, final_tree)
        metadata = {
            "format_version": FORMAT_VERSION,
            "run_id": record.run_id,
            "candidate_hash": record.candidate.hash,
            "baseline": {
                "tree": base_tree,
                "commit": commit,
                "bundle": f"{BASELINES}/{base_tree}.bundle",
                "content_digest": record.run_metadata["benchmark_input"]["workspace_digest"],
            },
            "graded": {
                "source": record.run_metadata["grading_source"]["selected"],
                "tree": final_tree,
                "content_digest": recorded,
            },
            "patch": {
                "path": PATCH,
                "sha256": digest(patch.read_bytes()),
                "bytes": patch.stat().st_size,
                "files_changed": len([p for p in changed.split(b"\0") if p]),
            },
            "grading_copy_omits": GRADING_COPY_OMITS,
            "archived_at": datetime.now(UTC).isoformat(),
        }
        # Rebuild from exactly the bytes that would be written, in a fresh repository.
        _rebuild(
            Scratch(scratch_root / "reader"), bundle, patch, metadata, scratch_root / "rebuilt"
        )
        if dry_run:
            return {"status": "would_archive", "bytes": metadata["patch"]["bytes"]}
        with _lock(results_repo):
            if (target / METADATA).is_file():
                return {"status": "exists", "path": str(target.relative_to(results_repo))}
            _write_baseline(results_repo, base_tree, bundle, scratch_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".workspace-", dir=target.parent))
            try:
                shutil.copyfile(patch, staging / PATCH)
                (staging / METADATA).write_bytes(canonical(metadata) + b"\n")
                # Repository files, readable like any other checkout content.
                staging.chmod(0o755)
                os.rename(staging, target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
    return {
        "status": "archived",
        "path": str(target.relative_to(results_repo)),
        "bytes": metadata["patch"]["bytes"],
    }


def _write_baseline(results_repo: Path, tree: str, bundle: Path, scratch_root: Path) -> None:
    """Write the baseline once; an existing one is verified to hold the same tree, never replaced."""
    path = baseline_path(results_repo, tree)
    if path.exists():
        Scratch(scratch_root / "existing").unbundle(path, tree)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".baseline-", dir=path.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(bundle, temporary)
        os.chmod(temporary, 0o644)
        os.rename(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


SKIPPED = {"run_artifacts_unavailable", "no_graded_workspace"}


def backfill(results_repo: Path, results_dir: Path, *, runs=(), dry_run: bool = False) -> list:
    """Archive every recorded run whose artifacts this host holds; one row per record.

    A record from another host is skipped (its artifacts are there), as is a run that
    produced no graded workspace; every other failure is a refusal with its reason.
    """
    from silverquillm.results_repo import InvalidRunRecordError, iter_run_dirs

    from .records import read_record

    rows = []
    for record_dir in iter_run_dirs(results_repo):
        if runs and not any(record_dir.name.startswith(run) for run in runs):
            continue
        try:
            record = read_record(record_dir)
        except InvalidRunRecordError:
            continue  # Schema 1 records predate Karn workspaces.
        row = {"run_id": record.run_id, "candidate_hash": record.candidate.hash}
        execution_run_id = record.run_metadata.get("execution_run_id", record.run_id)
        run_dir = Path(results_dir).resolve() / str(execution_run_id)
        try:
            if not RUN_ID.fullmatch(str(execution_run_id)) or not run_dir.is_dir():
                raise ArchiveRefused("run_artifacts_unavailable")
            row.update(archive_run(results_repo, record, run_dir, dry_run=dry_run))
        except ArchiveRefused as refused:
            reason = str(refused)
            row.update(status="skipped" if reason in SKIPPED else "refused", reason=reason)
        rows.append(row)
    return rows
