#!/usr/bin/env python3
"""Stage run records from the private Results Repo into the bench repo's
public ``published/`` tree (issue #39 §4, #66 Part A).

The publish script is a **porter with two checks, never a librarian**: it
copies ``manifest.json`` + ``scores.json`` of explicitly named runs into a
destination the operator chooses, and it never commits — the operator reviews
the staged diff and commits, and that commit is the approval stamp.

The two checks, per run:

- **Traceability — a hard refusal.**  The run's candidate identity must exist
  under ``candidates/`` (``candidates/<slug>--<hash8>/``) and verify by
  recomputation: the checked-in bundle is ingested through the bench's own
  path (TheOzolith's verifier, identity recomputed from bundle bytes) and its
  candidate hash and identity triple must equal the record's.  An absent
  candidate, a mismatch, a bundle that fails verification, or a ``legacy``
  identity (which has no bundle) refuses the whole publication.  When the
  Results Repo holds the vendored copy at ``results/<hash>/candidate/`` it is
  re-verified too.
- **Validity — a warning.**  ``leaderboard_valid: false`` (a Resume Leg, a
  gate-failed or unevaluated run, an ineligible benchmark) is reported and
  refuses unless ``--allow-invalid`` is passed: publishable at the operator's
  discretion, and never able to enter a leaderboard because tooling filters
  on the flag mechanically.

**Publication is a transaction.**  Every run is checked before the first
byte is written; an already-published byte-identical record is skipped; a
differing record under the same destination is a conflict that refuses.  The
new records are then copied into a private staging directory beside the
destination (``<dest>/.publish-staging-<nonce>/``), re-read and proven byte
identical to their sources, and only then committed — one atomic rename per
record directory — under an on-disk journal (``<dest>/.publish-journal.json``)
that names exactly the directories this invocation creates.  Any failure
rolls back every directory the transaction created and leaves pre-existing
records untouched; an interrupted transaction is finished (rolled back, or
completed when every record had already been committed) at the start of the
next invocation, from its journal.  A rollback that itself fails is reported
prominently, the journal stays, and no further publication into that
destination proceeds until recovery succeeds.  The success summary prints
only after the transaction commits.

**One invocation per destination.**  Recovery, planning, staging, commit,
finish and rollback all run under an exclusive per-destination lock — an
advisory ``flock`` on the destination directory itself
(:class:`PublicationLock`), so it leaves no artifact under the destination
or in the operator's commit, and it is never inferred from a recorded pid
or hostname, which a reused pid or a copied file could fake.  A second live
invocation refuses rather than recover a journal that belongs to a
transaction still in flight; once the holder has exited — the kernel drops
the lock with the process — the next invocation recovers whatever journal
it left.  A live transaction and a stale journal therefore never look
alike: the first holds the lock, the second cannot.  ``--dry-run`` takes a
shared hold, so it reports a transaction in flight as exactly that, never
as an interrupted one awaiting recovery.  An exclusive hold creates an
absent destination for the lifecycle and, when the invocation published
nothing, removes it on release — only if the path still names the very
directory it created (device and inode) and that directory is empty.  A
replacement, or content something else wrote there meanwhile, is never
removed, and that, like a removal that fails, is a
:class:`PublicationCleanupError` (``CLEANUP FAILED``, exit 2) naming what
is kept: a refusal over residue is never reported as clean.

**Beginning is all-or-nothing too.**  Once the journal exists, every
failure — duplicating its descriptor, writing it, closing either
descriptor, creating the staging directory — is an initialization failure:
the attempt removes what it created (the staging directory, then the
journal, proven to be the very file it made: a regular file with the
created file's device and inode, still linked while a descriptor of it is
open, or reading back as exactly the bytes written once none is) and
refuses with the cause chained.  Every descriptor is closed on every path.
If even that removal fails, the evidence stays and the failure says exactly
what is left and how to recover it, so no empty or half-written journal is
ever left for normal recovery to trip over.

**The journal is an untrusted filesystem boundary.**  It is the one thing
that grants recovery deletion authority, so it is trusted from nothing but a
real in-tree regular file: it is opened without following a link (a
symlinked journal — dangling or pointing at a valid-looking journal
elsewhere — is refused, never read), the type is proven by ``fstat`` on the
very descriptor that is then read (so a swap between check and read cannot
change what is read), and a directory, FIFO, socket or device under its
name is refused explicitly.  Both recovery and the read-only inspection
refuse the same way, with the destination unchanged.

**Recovery removes only what the journal proves the transaction created.**
Every name in the journal must be one plain child-name component of the
destination (the staging name in the exact format ``begin`` generates; no
separator, ``.``/``..`` or absolute path; no unexpected field, repeated name
or committing/committed inconsistency), and every derived cleanup target is
proven — before anything is removed — to be a real directory that resolves
to an immediate child of the destination and holds only what the
transaction copies: ``manifest.json`` and ``scores.json`` as regular files
(by ``lstat``, so a directory, symlink, FIFO, socket or device under either
name is refused — a directory could hold anything).  A record still in
staging may hold a subset of the two, because the process can die between
the copies; a committed record, or one whose rename landed while
``committing`` named it, must hold both.  A symlink anywhere is refused,
never followed.  A journal that fails any of this raises
:class:`PublicationRecoveryError`, keeps the journal, and leaves every
byte, name and mtime under the destination unchanged.

**``--dry-run`` is read-only.**  It never recovers: a pending journal is
inspected, the recovery that would occur is reported, and the exit status is
nonzero — the journal, staging tree, records, bytes and mtimes stay exactly
as they were.

**An artifact is what the tree holds, never what a link points at.**
Wherever the gate establishes that a candidate or a record is present in a
repository tree it proves the entry itself by ``lstat``: the curated
``candidates/<slug>--<hash8>/`` wrapper and its ``bundle/`` are real
directories resolving in place under ``candidates/`` (a symlink under a
candidate name is a hard refusal, never followed — the run would otherwise
be traced to content outside the repository); the source run record is
proven through every ancestor — the Results Repo's ``results/`` directory,
the candidate-hash directory and the run directory are real directories and
``manifest.json`` and ``scores.json`` regular files, so a record reached
through a symlinked ancestor is never publishable however valid its target
— and the complete proof is repeated immediately before each copy, so a
substitution after planning is refused and rolled back; a destination record
is recognized as "already published (identical)" only when it is a real
directory holding both record files as regular files; and discovery never
follows a symlinked directory or accepts a symlinked record file.

Discovery of published results (:func:`iter_published_records`) goes through
manifests only — never a path convention — so the operator organizes
``published/`` freely.

Usage::

    python scripts/publish_results.py --results-repo <clone> --dest published/<subdir> RUN_ID...
        [--candidates-dir candidates] [--allow-invalid] [--dry-run]
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn, Self

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import BUNDLE_SUBDIR, CandidateRefusedError, load_candidate_bundle
from silverquillm.results_repo import (
    MANIFEST_FILENAME,
    OZOLITH_SCHEME,
    RESULTS_DIRNAME,
    RESULTS_REPO_ENV,
    SCORES_FILENAME,
    CandidateIdentity,
    ResultsRepoError,
    RunRecord,
    candidate_copy_dir,
    candidate_hash,
    candidate_hash8,
    read_run_record,
    resolve_results_repo,
)

DEFAULT_CANDIDATES_DIR = REPO_ROOT / "candidates"
DEFAULT_PUBLISHED_DIR = REPO_ROOT / "published"
RECORD_FILES = (MANIFEST_FILENAME, SCORES_FILENAME)
#: The transaction journal, beside the records under the destination.
JOURNAL_FILENAME = ".publish-journal.json"
JOURNAL_SCHEMA_VERSION = 1
STAGING_PREFIX = ".publish-staging-"


class PublicationRefused(Exception):
    """The publication cannot proceed; nothing new is published."""


class PublicationRecoveryError(Exception):
    """A rollback (or the recovery of an interrupted transaction) failed:
    the destination may hold a partial publication.  The journal stays in
    place and no further publication into that destination proceeds until
    recovery succeeds."""


class PublicationLockedError(PublicationRefused):
    """Another invocation holds the destination: a transaction into it is in
    flight.  This one refuses outright — it never recovers, plans over or
    stages beside a live transaction."""


class PublicationCleanupError(Exception):
    """The invocation published nothing, but the empty destination it had
    created for the lifecycle is not restored: it could not be removed, the
    path no longer names it, or it is no longer empty.  Nothing is removed
    that the invocation cannot prove it created and left empty, and the
    outcome is never reported as a clean refusal.  *path* is the destination
    as kept; *refusal* the refusal in flight when cleanup ran, if any."""

    def __init__(self, message: str, *, path: Path, refusal: PublicationRefused | None) -> None:
        super().__init__(message)
        self.path = path
        self.refusal = refusal


@dataclass(frozen=True)
class Traceability:
    """Where the run's candidate identity is checked in, verified."""

    candidate_dir: Path
    candidate_hash: str
    vendored_copy_verified: bool


@dataclass
class PlannedRun:
    run_id: str
    source_dir: Path
    record: RunRecord
    dest_dir: Path
    traceability: Traceability | None = None
    refusals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    already_staged: bool = False


@dataclass
class PublicationPlan:
    dest: Path
    runs: list[PlannedRun]
    #: Where the source records live: the transaction re-proves every source
    #: through every ancestor immediately before it copies.
    results_repo: Path

    @property
    def refusals(self) -> list[str]:
        return [f"{run.run_id}: {reason}" for run in self.runs for reason in run.refusals]

    @property
    def warnings(self) -> list[str]:
        return [f"{run.run_id}: {reason}" for run in self.runs for reason in run.warnings]

    @property
    def to_stage(self) -> list[PlannedRun]:
        return [run for run in self.runs if not run.already_staged]


# ---------------------------------------------------------------------------
# Locating records
# ---------------------------------------------------------------------------


def source_record_dir(results_repo: Path, run_id: str) -> Path:
    """The one ``results/<candidate-hash>/<run-id>/`` of *results_repo* named
    *run_id*, proven a real in-tree record through every ancestor: the
    ``results/`` directory and the candidate-hash directory are real
    directories by ``lstat``, so is the run directory, and both record files
    are regular files.  A symlink or special file at any component refuses,
    never followed — a record reached through a link is content outside the
    Results Repo, whatever it resolves to.  An entry under ``results/`` that
    is neither a directory nor a link is no component of any record's path
    and is passed over.  Zero or several matches refuse.

    The Results Repo root itself is the operator's ``--results-repo``
    argument and is taken as given; containment is proven from ``results/``
    down."""
    results_dir = Path(results_repo) / RESULTS_DIRNAME
    _require_real_directory(results_dir, "the Results Repo's results directory")
    matches: list[Path] = []
    for entry in sorted(results_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        mode = _lstat_mode(entry)
        if mode is None:
            continue
        if stat.S_ISLNK(mode):
            raise PublicationRefused(
                f"{entry} is a symlink — a Results Repo keeps its records under real"
                " candidate-hash directories, never behind a link to content elsewhere;"
                " refusing to follow it"
            )
        if not stat.S_ISDIR(mode):
            continue
        run_dir = entry / run_id
        if _lstat_mode(run_dir) is None:
            continue
        _require_real_directory(run_dir, "the run record directory")
        matches.append(run_dir)
    if not matches:
        raise PublicationRefused(f"no run record named {run_id!r} in {results_repo}")
    if len(matches) > 1:
        raise PublicationRefused(
            f"run id {run_id!r} is ambiguous in {results_repo}: "
            + ", ".join(str(m) for m in matches)
        )
    run_dir = matches[0]
    for name in RECORD_FILES:
        _require_regular_file(run_dir / name, "the run record file")
    in_place = Path(os.path.realpath(results_dir)) / run_dir.parent.name / run_id
    if Path(os.path.realpath(run_dir)) != in_place:
        raise PublicationRefused(
            f"{run_dir} does not resolve in place under {results_dir}; refusing to publish a"
            " record reached through a link"
        )
    return run_dir


def find_run_record(results_repo: Path, run_id: str) -> tuple[Path, RunRecord]:
    """The one record named *run_id* (:func:`source_record_dir`), re-proven
    on read."""
    run_dir = source_record_dir(results_repo, run_id)
    try:
        return run_dir, read_run_record(run_dir)
    except ResultsRepoError as exc:
        raise PublicationRefused(f"{run_id}: the record does not re-prove on read: {exc}") from exc


# ---------------------------------------------------------------------------
# In-tree proofs: an artifact is what the tree holds, never what a link
# points at.  Every predicate here is ``lstat``-based — the type of the entry
# itself — so a symlink is refused, never followed, wherever the gate
# establishes that a candidate or a record is present in a repository tree.
# ---------------------------------------------------------------------------


def _file_kind(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "a directory"
    if stat.S_ISLNK(mode):
        return "a symlink"
    if stat.S_ISFIFO(mode):
        return "a FIFO"
    if stat.S_ISSOCK(mode):
        return "a socket"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "a device"
    return "a special file"


def _lstat_mode(path: Path) -> int | None:
    """The ``lstat`` mode of *path*, or ``None`` when nothing is there."""
    try:
        return os.lstat(path).st_mode
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PublicationRefused(f"cannot inspect {path}: {exc}") from exc


def _require_real_directory(path: Path, what: str) -> None:
    """*path* is a directory in the tree itself — not a symlink to one, which
    is refused rather than followed — or :class:`PublicationRefused`."""
    mode = _lstat_mode(path)
    if mode is None:
        raise PublicationRefused(f"{what} {path} does not exist")
    if stat.S_ISLNK(mode):
        raise PublicationRefused(
            f"{what} {path} is a symlink — a public artifact is a real directory in the"
            " repository tree, never a link to content elsewhere; refusing to follow it"
        )
    if not stat.S_ISDIR(mode):
        raise PublicationRefused(f"{what} {path} is {_file_kind(mode)}, not a directory")


def _require_regular_file(path: Path, what: str) -> None:
    """*path* is a regular file by ``lstat`` — a symlink, directory or special
    file under the name is refused, never read through."""
    mode = _lstat_mode(path)
    if mode is None:
        raise PublicationRefused(f"{what} {path} does not exist")
    if not stat.S_ISREG(mode):
        raise PublicationRefused(
            f"{what} {path} is {_file_kind(mode)}, not a regular file — a public artifact"
            " holds regular files only; refusing to read through it"
        )


def _is_regular_file(path: Path) -> bool:
    mode = _lstat_mode(path)
    return mode is not None and stat.S_ISREG(mode)


#: Open without following a link, without blocking on a FIFO, and hand the
#: descriptor to ``fstat`` — the type is proven on the object that will be
#: read, so nothing swapped in between a check and the read can change it.
_NOFOLLOW_READ = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def _copy_regular_file(source: Path, target: Path) -> None:
    """Copy *source* to *target* through a descriptor opened without following
    a link and proven a regular file, so the bytes copied are the bytes that
    were proven."""
    try:
        fd = os.open(source, _NOFOLLOW_READ)
    except OSError as exc:
        raise PublicationRefused(f"cannot open the run record file {source}: {exc.strerror or exc}") from exc
    mode = os.fstat(fd).st_mode
    if not stat.S_ISREG(mode):
        os.close(fd)
        raise PublicationRefused(
            f"the run record file {source} is {_file_kind(mode)}, not a regular file;"
            " refusing to read through it"
        )
    with os.fdopen(fd, "rb") as fh:
        target.write_bytes(fh.read())


# ---------------------------------------------------------------------------
# The two checks
# ---------------------------------------------------------------------------


def _candidate_dirs_with_hash8(candidates_dir: Path, hash8: str) -> list[Path]:
    """The ``<slug>--<hash8>`` entries of *candidates_dir* that are real
    directories in the tree.  A symlink under a candidate name is a hard
    refusal, never followed: the curated candidate is what the repository
    holds, not what a link on this host points at."""
    if not candidates_dir.is_dir():
        return []
    suffix = f"--{hash8}"
    dirs: list[Path] = []
    for entry in sorted(candidates_dir.iterdir()):
        if entry.name.startswith(".") or not entry.name.endswith(suffix):
            continue
        mode = os.lstat(entry).st_mode
        if stat.S_ISLNK(mode):
            raise PublicationRefused(
                f"{entry} is a symlink — a curated candidate is a real directory under"
                f" {candidates_dir}, never a link to content elsewhere; refusing to follow it"
            )
        if stat.S_ISDIR(mode):
            dirs.append(entry)
    return dirs


def check_traceability(
    identity: CandidateIdentity, *, candidates_dir: Path, results_repo: Path | None = None
) -> Traceability:
    """The traceability check: *identity* is checked in under *candidates_dir*
    and verifies by recomputation.  Raises :class:`PublicationRefused`."""
    if identity.scheme != OZOLITH_SCHEME:
        raise PublicationRefused(
            f"the run's candidate identity is scheme {identity.scheme!r}, which has no"
            " Candidate Bundle to trace to — only a run driven from a verified bundle"
            f" ({OZOLITH_SCHEME}) is publishable"
        )
    expected_hash = candidate_hash(identity)
    hash8 = candidate_hash8(identity)
    dirs = _candidate_dirs_with_hash8(candidates_dir, hash8)
    if not dirs:
        raise PublicationRefused(
            f"no candidate under {candidates_dir} carries identity hash {expected_hash}"
            f" (hash8 {hash8}) — promote the candidate first"
            " (scripts/promote_candidate.py); a result whose candidate is not public"
            " is untraceable and cannot be published"
        )
    if len(dirs) > 1:
        raise PublicationRefused(
            f"identity hash8 {hash8} names several candidate directories"
            f" ({', '.join(d.name for d in dirs)}); candidates/ must be flat and"
            " deduplicating"
        )
    candidate_dir = dirs[0]
    if Path(os.path.realpath(candidate_dir)).parent != Path(os.path.realpath(candidates_dir)):
        raise PublicationRefused(
            f"{candidate_dir} does not resolve to an immediate child of {candidates_dir};"
            " refusing to trace a run to content outside the curated candidates directory"
        )
    _require_real_directory(candidate_dir / BUNDLE_SUBDIR, "the curated candidate's bundle directory")
    try:
        bundle = load_candidate_bundle(candidate_dir)
    except CandidateRefusedError as exc:
        raise PublicationRefused(
            f"{candidate_dir} fails verification, so the run cannot be traced to a"
            f" verified candidate: {exc}"
        ) from exc
    recomputed = bundle.identity
    if bundle.candidate_hash != expected_hash or (
        recomputed.base_image_digest,
        recomputed.instruction_hash,
        recomputed.adapter_identity,
    ) != (identity.base_image_digest, identity.instruction_hash, identity.adapter_identity):
        raise PublicationRefused(
            f"{candidate_dir} recomputes to candidate hash {bundle.candidate_hash}"
            f" {recomputed.to_dict()}, but the record carries {expected_hash}"
            f" {identity.to_dict()} — identity is never trusted from a recorded value"
        )
    vendored_verified = False
    if results_repo is not None:
        copy = candidate_copy_dir(results_repo, identity)
        if copy.exists():
            try:
                summary = ozcandidate.verify_bundle(copy)
            except ozcandidate.CandidateError as exc:
                raise PublicationRefused(
                    f"the vendored candidate copy {copy} fails verification: {exc}"
                ) from exc
            vendored = CandidateIdentity.recomputed(
                summary.base_digest, summary.instruction_hash, summary.adapter
            )
            if candidate_hash(vendored) != expected_hash:
                raise PublicationRefused(
                    f"the vendored candidate copy {copy} recomputes to"
                    f" {candidate_hash(vendored)}, not the record's {expected_hash}"
                )
            vendored_verified = True
    return Traceability(
        candidate_dir=candidate_dir,
        candidate_hash=expected_hash,
        vendored_copy_verified=vendored_verified,
    )


def validity_warnings(record: RunRecord) -> list[str]:
    """Every reason the run is not leaderboard-valid; empty means valid."""
    if record.leaderboard_valid:
        return []
    reasons = [f"leaderboard_valid is false for benchmark {record.benchmark!r}"]
    note = record.run_metadata.get("validity_note")
    if isinstance(note, str) and note:
        reasons.append(note)
    if record.resumed_from:
        reasons.append(f"Resume Leg (resumed_from={record.resumed_from})")
    if record.run_metadata.get("evaluated") is False:
        reasons.append("the run was never evaluated (scores are zeroed placeholders)")
    failure = record.run_metadata.get("failure")
    if isinstance(failure, dict) and failure.get("class"):
        reasons.append(f"classified failure {failure['class']!r} at {failure.get('phase')!r}")
    return reasons


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def _same_bytes(a: Path, b: Path) -> bool:
    return _is_regular_file(a) and _is_regular_file(b) and a.read_bytes() == b.read_bytes()


def plan_publication(
    run_ids: list[str],
    *,
    results_repo: Path,
    dest: Path,
    candidates_dir: Path,
    allow_invalid: bool,
) -> PublicationPlan:
    """Check every run before anything is staged.  Refusals accumulate per run
    so the operator sees them all at once; the caller stages only a plan with
    none."""
    if not run_ids:
        raise PublicationRefused("no run ids given")
    if len(set(run_ids)) != len(run_ids):
        raise PublicationRefused("run ids repeat: " + ", ".join(sorted({r for r in run_ids if run_ids.count(r) > 1})))
    dest = Path(dest)
    if _lstat_mode(journal_path(dest)) is not None:
        raise PublicationRefused(
            f"{journal_path(dest)} exists: an earlier publication into {dest} was"
            " interrupted — run the script again: under the destination lock it recovers"
            " the journal before planning new work (a transaction still in flight holds"
            " that lock and refuses a second invocation outright)"
        )
    plan = PublicationPlan(dest=dest, runs=[], results_repo=Path(results_repo))
    for run_id in run_ids:
        source_dir, record = find_run_record(results_repo, run_id)
        planned = PlannedRun(run_id=run_id, source_dir=source_dir, record=record, dest_dir=plan.dest / run_id)
        plan.runs.append(planned)
        try:
            planned.traceability = check_traceability(
                record.candidate, candidates_dir=candidates_dir, results_repo=results_repo
            )
        except PublicationRefused as exc:
            planned.refusals.append(f"untraceable: {exc}")
        warnings = validity_warnings(record)
        planned.warnings.extend(warnings)
        if warnings and not allow_invalid:
            planned.refusals.append(
                "leaderboard_valid is false; pass --allow-invalid to publish it anyway"
                " (it can never enter a leaderboard: tooling filters on the flag)"
            )
        if planned.dest_dir.exists() or planned.dest_dir.is_symlink():
            try:
                _require_real_directory(planned.dest_dir, "the published record directory")
                for name in RECORD_FILES:
                    _require_regular_file(planned.dest_dir / name, "the published record file")
            except PublicationRefused as exc:
                planned.refusals.append(
                    f"{exc}: only a real directory holding both record files as regular files"
                    " can be recognized as already published, and a published record is"
                    " never overwritten; resolve by hand"
                )
            else:
                if all(_same_bytes(source_dir / name, planned.dest_dir / name) for name in RECORD_FILES):
                    planned.already_staged = True
                else:
                    planned.refusals.append(
                        f"{planned.dest_dir} already exists with different content — a"
                        " published record is never overwritten; resolve by hand"
                    )
    return plan


# ---------------------------------------------------------------------------
# Serialization: one invocation per destination
# ---------------------------------------------------------------------------


@dataclass
class _HeldLock:
    fd: int
    depth: int
    exclusive: bool
    created_dest: bool


#: The destinations this process holds locked, by directory identity, so the
#: phases of one invocation (recover, plan, stage, commit, finish, roll back)
#: nest under a single hold instead of contending with each other.
_HELD_LOCKS: dict[tuple[int, int], _HeldLock] = {}


class PublicationLock:
    """The one invocation allowed to recover, plan, stage, commit, finish or
    roll back a publication into a destination at a time.

    The lock is an advisory ``flock`` on a descriptor of the destination
    directory *itself*, so it leaves no artifact: nothing under the
    destination, nothing for the operator to commit or clean up, nothing a
    replacement host could mistake for a live holder.  The kernel drops it
    with the process — an invocation that dies holding it releases it, and
    the next one recovers the journal it left — and it is never inferred
    from a recorded pid or hostname, which a reused pid or a copied file
    could fake.  A second live invocation refuses
    (:class:`PublicationLockedError`) rather than wait: it must never
    recover a journal that belongs to a transaction still in flight.  Two
    processes are what the lock arbitrates; within one process the phases
    re-enter the same hold.

    Exclusive (the default) creates the destination when it is absent and,
    on release, removes it again when this invocation published nothing into
    it — only if the path still names the very directory it created (device
    and inode) and that directory is empty, so a refused plan leaves nothing
    behind and nothing of anyone else's is ever removed; anything less is a
    :class:`PublicationCleanupError` naming what is kept
    (:meth:`_remove_created`).  A hold under which records were committed
    marks the destination kept (:meth:`keep_dest`), and one released by a
    :class:`PublicationRecoveryError` keeps it too: the journal that error
    retains lives there.  ``shared`` is the
    read-only dry run's hold: it never creates anything, coexists with
    other shared holds, and is refused while an exclusive hold is live, so
    a dry run reports an in-flight transaction as such instead of as an
    interrupted one.
    """

    def __init__(self, dest: Path, *, shared: bool = False) -> None:
        self.dest = Path(dest)
        self.shared = shared
        self._key: tuple[int, int] | None = None

    @property
    def held(self) -> bool:
        return self._key is not None

    def __enter__(self) -> Self:
        created: tuple[int, int] | None = None
        while True:
            try:
                identity = os.stat(self.dest)
            except FileNotFoundError:
                if self.shared:
                    return self  # nothing there: nothing to lock, nothing to inspect
                created = self._create_dest() or created
                continue
            key = (identity.st_dev, identity.st_ino)
            held = _HELD_LOCKS.get(key)
            if held is not None:
                self._reenter(held)
                self._key = key
                return self
            try:
                fd = os.open(self.dest, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            except OSError as exc:
                raise PublicationRefused(f"cannot open the destination {self.dest}: {exc.strerror or exc}") from exc
            try:
                fcntl.flock(fd, (fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise PublicationLockedError(self._busy()) from None
            except OSError as exc:
                os.close(fd)
                raise PublicationRefused(f"cannot lock the destination {self.dest}: {exc.strerror or exc}") from exc
            locked = os.fstat(fd)
            try:
                current = os.stat(self.dest)
            except FileNotFoundError:
                current = None
            if current is None or (current.st_dev, current.st_ino) != (locked.st_dev, locked.st_ino):
                # The directory we locked is no longer what the path names —
                # a releasing invocation removed the empty destination it had
                # created.  Lock what the path names now.
                os.close(fd)
                continue
            key = (locked.st_dev, locked.st_ino)
            # What this hold locked is the directory it created only if the
            # identities agree; otherwise it locked what the path names now.
            _HELD_LOCKS[key] = _HeldLock(fd=fd, depth=1, exclusive=not self.shared, created_dest=created == key)
            self._key = key
            return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        key = self._key
        if key is None:
            return
        self._key = None
        held = _HELD_LOCKS[key]
        held.depth -= 1
        if held.depth:
            return
        del _HELD_LOCKS[key]
        try:
            # Still under the lock, so a waiter that locks this directory
            # re-checks the path's identity and never keeps a lock on a
            # removed one.  A recovery error keeps its journal under the
            # destination: that destination is evidence, not residue.
            if held.created_dest and not isinstance(exc, PublicationRecoveryError):
                self._remove_created(key, refusal=exc if isinstance(exc, PublicationRefused) else None)
        finally:
            fcntl.flock(held.fd, fcntl.LOCK_UN)
            os.close(held.fd)

    def keep_dest(self) -> None:
        """The destination now holds what this invocation came to put there:
        it is no longer an empty directory the hold removes on release."""
        if self._key is not None:
            _HELD_LOCKS[self._key].created_dest = False

    def _create_dest(self) -> tuple[int, int] | None:
        """Create the absent destination; return the identity (device, inode)
        of the directory this call created, ``None`` when another party made
        it first — only a directory this invocation created is ever removed."""
        try:
            self.dest.mkdir(parents=True)
        except FileExistsError:
            if os.path.isdir(self.dest):
                return None  # another invocation created it first
            raise PublicationRefused(
                f"the destination {self.dest} exists but is not a directory; refusing to use it"
            ) from None
        except OSError as exc:
            raise PublicationRefused(f"cannot create the destination {self.dest}: {exc.strerror or exc}") from exc
        try:
            made = os.lstat(self.dest)
        except OSError as exc:
            raise PublicationRefused(f"created the destination {self.dest} but cannot inspect it: {exc.strerror or exc}") from exc
        return (made.st_dev, made.st_ino) if stat.S_ISDIR(made.st_mode) else None

    def _remove_created(self, identity: tuple[int, int], *, refusal: PublicationRefused | None) -> None:
        """Remove the destination this hold created — only if the path still
        names that very directory (*identity*: device and inode) and it is
        empty.  A replacement or another party's content is never removed;
        that, and a removal that fails, is a :class:`PublicationCleanupError`
        naming what is kept, with *refusal* attached."""
        dest = self.dest
        nothing = f"the destination {dest} this invocation created for a publication that published nothing"
        try:
            now = os.lstat(dest)
        except FileNotFoundError:
            return  # already gone: nothing of this invocation's is left
        except OSError as exc:
            raise PublicationCleanupError(
                f"{nothing} cannot be inspected ({exc.strerror or exc}) and may be left behind — check it"
                f" and remove it by hand if it is empty (rmdir {dest})",
                path=dest,
                refusal=refusal,
            ) from exc
        if not stat.S_ISDIR(now.st_mode) or (now.st_dev, now.st_ino) != identity:
            raise PublicationCleanupError(
                f"{dest} no longer names the empty directory this invocation created; what is there"
                " now is someone else's and is kept — inspect it by hand",
                path=dest,
                refusal=refusal,
            )
        try:
            os.rmdir(dest)
        except FileNotFoundError:
            return
        except OSError as exc:
            if exc.errno in (errno.ENOTEMPTY, errno.EEXIST):
                message = (
                    f"{nothing} is not empty — something else wrote into it meanwhile; it is kept with"
                    " its contents, which are not this invocation's to remove — inspect it by hand"
                )
            else:
                message = f"{nothing} could not be removed ({exc.strerror or exc}); remove it by hand (rmdir {dest})"
            raise PublicationCleanupError(message, path=dest, refusal=refusal) from exc

    def _reenter(self, held: _HeldLock) -> None:
        if not self.shared and not held.exclusive:
            try:
                fcntl.flock(held.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PublicationLockedError(self._busy()) from None
            held.exclusive = True
        held.depth += 1

    def _busy(self) -> str:
        return (
            f"another publication invocation holds {self.dest}: a transaction into it is in"
            " flight, and a second invocation never recovers, plans over or stages beside a"
            " live one — let it exit and run again (a transaction it leaves interrupted is"
            " recovered then, from its journal)"
        )


# ---------------------------------------------------------------------------
# The transaction: private staging, byte-proven copies, journaled commit
# ---------------------------------------------------------------------------


def journal_path(dest: Path) -> Path:
    return Path(dest) / JOURNAL_FILENAME


#: The staging directory's exact name: the prefix and the 4-byte hex nonce
#: ``begin`` draws — a journal naming anything else was not written by this
#: script.
_STAGING_NAME_RE = re.compile(re.escape(STAGING_PREFIX) + r"[0-9a-f]{8}")
#: One plain directory-name component: never dot-prefixed, so never ``.`` or
#: ``..``; no separator of any kind.
_RECORD_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_JOURNAL_KEYS = frozenset({"schema_version", "staging", "planned", "committing", "committed"})


def _safe_record_name(name: object) -> bool:
    return isinstance(name, str) and _RECORD_NAME_RE.fullmatch(name) is not None


@dataclass
class Journal:
    """What one publication transaction created under its destination — and
    nothing else: only names listed here are ever removed by a rollback.

    ``planned`` are the record directories the transaction will create (none
    existed when it began); ``committing`` is the one whose rename may be in
    flight; ``committed`` are the ones renamed into place.  ``staging`` is
    the private sibling directory holding the not-yet-committed copies.
    Every name is one plain child-name component of the destination: a
    journal that says otherwise was not written by this script and is
    refused whole (:class:`PublicationRecoveryError`) before anything is
    touched.
    """

    staging: str
    planned: list[str]
    committing: str | None = None
    committed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "staging": self.staging,
            "planned": list(self.planned),
            "committing": self.committing,
            "committed": list(self.committed),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Journal:
        if not isinstance(data, dict):
            raise PublicationRecoveryError("malformed journal: not a JSON object")
        if data.get("schema_version") != JOURNAL_SCHEMA_VERSION:
            raise PublicationRecoveryError(
                f"unrecognized journal (schema_version {data.get('schema_version')!r})"
            )
        if set(data) != _JOURNAL_KEYS:
            raise PublicationRecoveryError(
                "malformed journal: unexpected or missing fields"
                f" ({', '.join(sorted(set(data) ^ _JOURNAL_KEYS))})"
            )
        staging = data["staging"]
        planned = data["planned"]
        committing = data["committing"]
        committed = data["committed"]
        if not isinstance(staging, str) or _STAGING_NAME_RE.fullmatch(staging) is None:
            raise PublicationRecoveryError(
                "malformed journal: staging is not a staging directory name"
                f" ({STAGING_PREFIX}<8 hex digits>)"
            )
        if not isinstance(planned, list) or not planned or not all(_safe_record_name(name) for name in planned):
            raise PublicationRecoveryError(
                "malformed journal: planned must be a non-empty list of plain record directory names"
            )
        if len(set(planned)) != len(planned):
            raise PublicationRecoveryError("malformed journal: planned names repeat")
        if not isinstance(committed, list) or not all(name in planned for name in committed):
            raise PublicationRecoveryError("malformed journal: committed names a directory that was never planned")
        if len(set(committed)) != len(committed):
            raise PublicationRecoveryError("malformed journal: committed names repeat")
        if committing is not None and (committing not in planned or committing in committed):
            raise PublicationRecoveryError(
                "malformed journal: committing must name one planned, not yet committed record"
            )
        return cls(staging=staging, planned=list(planned), committing=committing, committed=list(committed))

    @property
    def complete(self) -> bool:
        return self.committing is None and set(self.committed) == set(self.planned)


def _write_whole(fd: int, data: bytes) -> None:
    """Write *data* to *fd* completely, then close it.  A short write is
    continued; an error from the write or the close propagates, with the
    descriptor closed either way."""
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def _read_whole(fd: int, limit: int) -> bytes:
    """Up to *limit* bytes from *fd*, from its current position."""
    chunks: list[bytes] = []
    while limit > 0:
        chunk = os.read(fd, limit)
        if not chunk:
            break
        chunks.append(chunk)
        limit -= len(chunk)
    return b"".join(chunks)


def _write_journal(path: Path, journal: Journal) -> None:
    """Atomic replace, so the journal always parses."""
    payload = json.dumps(journal.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".publish-journal-", suffix=".tmp", dir=path.parent)
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


def _not_a_journal(path: Path, mode: int) -> PublicationRecoveryError:
    if stat.S_ISLNK(mode):
        return PublicationRecoveryError(
            f"{path} is a symlink — the journal is a regular file the transaction writes beside"
            " its records, never a link; refusing to follow it"
        )
    return PublicationRecoveryError(
        f"{path} is {_file_kind(mode)}, not a regular file — the journal is a regular file the"
        " transaction writes beside its records; refusing to read it"
    )


def _open_journal(path: Path) -> int | None:
    """A read descriptor on the journal at *path*, or ``None`` when nothing
    is there.  The journal is the only thing that grants recovery deletion
    authority, so it is trusted from nothing but a real in-tree regular
    file: the open never follows a link (a dangling one is refused like any
    other), never blocks on a FIFO, and the type is proven by ``fstat`` on
    the descriptor that is then read — a directory, symlink, FIFO, socket or
    device under the journal's name is refused, never read through."""
    try:
        fd = os.open(path, _NOFOLLOW_READ)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise _not_a_journal(path, stat.S_IFLNK) from None
        try:
            mode = os.lstat(path).st_mode
        except OSError:
            mode = None
        if mode is not None and not stat.S_ISREG(mode):
            raise _not_a_journal(path, mode) from None
        raise PublicationRecoveryError(f"cannot open {path}: {exc.strerror or exc}") from exc
    try:
        mode = os.fstat(fd).st_mode
    except OSError as exc:
        os.close(fd)
        raise PublicationRecoveryError(f"cannot inspect {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        os.close(fd)
        raise _not_a_journal(path, mode)
    return fd


def _read_journal(path: Path) -> Journal | None:
    """The journal at *path* (``None`` when there is none), read through a
    descriptor proven to be a regular file (:func:`_open_journal`) and
    validated whole (:meth:`Journal.from_dict`)."""
    fd = _open_journal(path)
    if fd is None:
        return None
    try:
        with os.fdopen(fd, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicationRecoveryError(f"cannot read {path}: {exc}") from exc
    return Journal.from_dict(data)


def _removable_directory(parent: Path, name: str) -> Path | None:
    """``parent/name`` as a directory a recovery step may remove, or ``None``
    when nothing is there.  Proves the containment half of what a rollback
    needs: *name* is one validated component, and the entry is a real
    directory — never a symlink, which is refused rather than followed —
    that resolves to an immediate child of *parent*.  What the directory may
    hold is the other half: :func:`_validate_record` for a record,
    :func:`_validate_staging` for the staging tree."""
    if not (_safe_record_name(name) or _STAGING_NAME_RE.fullmatch(name)):
        raise PublicationRecoveryError(f"refusing to remove {name!r}: not a plain directory name")
    target = parent / name
    if target.parent != parent or target.name != name:
        raise PublicationRecoveryError(f"refusing to remove {name!r}: not an immediate child of {parent}")
    try:
        mode = os.lstat(target).st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode):
        raise PublicationRecoveryError(
            f"{target} is a symlink — the transaction created only real directories; refusing to"
            " follow it"
        )
    if not stat.S_ISDIR(mode):
        raise PublicationRecoveryError(f"{target} is not a directory; the transaction did not create it")
    if Path(os.path.realpath(target)).parent != Path(os.path.realpath(parent)):
        raise PublicationRecoveryError(f"{target} does not resolve to an immediate child of {parent}")
    return target


def _entry_modes(directory: Path) -> dict[str, int]:
    """Each entry of *directory* with its ``lstat`` mode: the type of the
    entry itself, never of what a link points at."""
    try:
        return {entry.name: os.lstat(entry).st_mode for entry in directory.iterdir()}
    except OSError as exc:
        raise PublicationRecoveryError(f"cannot inspect {directory}: {exc}") from exc


def _validate_record(target: Path, *, complete: bool) -> None:
    """*target* holds record files only, each a regular file — never a
    directory (which could hold anything), a symlink, a FIFO, a socket or a
    device: the transaction copies regular files and nothing else.  A record
    still in staging may hold a subset (the process can die between the two
    copies); a *complete* one — committed, or renamed into place while
    ``committing`` named it — holds every record file."""
    modes = _entry_modes(target)
    for name, mode in sorted(modes.items()):
        if name not in RECORD_FILES:
            raise PublicationRecoveryError(
                f"{target} holds {name!r}, which the transaction did not create; refusing to"
                " remove the directory"
            )
        if not stat.S_ISREG(mode):
            raise PublicationRecoveryError(
                f"{target / name} is {_file_kind(mode)}, not the regular file the transaction"
                f" copies; refusing to remove {target}"
            )
    missing = [name for name in RECORD_FILES if name not in modes]
    if complete and missing:
        raise PublicationRecoveryError(
            f"{target} lacks {', '.join(missing)}; a committed record holds every record file, so"
            " the transaction did not create this directory — refusing to remove it"
        )


def _validate_staging(staging: Path, planned: Iterable[str]) -> None:
    """*staging* holds only planned record directories, each a real directory
    holding a subset of the record files as regular files."""
    allowed = set(planned)
    for name in sorted(_entry_modes(staging)):
        if name not in allowed:
            raise PublicationRecoveryError(
                f"{staging} holds {name!r}, which the transaction did not create; refusing to"
                " remove the directory"
            )
        record = _removable_directory(staging, name)
        if record is not None:
            _validate_record(record, complete=False)


def _committed_targets(dest: Path, journal: Journal) -> list[str]:
    """The record names a rollback removes: the committed ones, plus the one
    whose rename landed before the journal could say so.  Reads only."""
    names = list(journal.committed)
    if journal.committing is not None:
        in_flight = journal.committing
        if os.path.lexists(dest / in_flight) and not os.path.lexists(dest / journal.staging / in_flight):
            names.append(in_flight)
    return names


def _validate_rollback(dest: Path, journal: Journal) -> tuple[list[tuple[str, Path | None]], Path | None]:
    """Every path a rollback will remove — the staging tree and each
    committed record, contents included — proven removable before any
    deletion, so a journal that fails the proof leaves the destination
    exactly as it was."""
    staging = _removable_directory(dest, journal.staging)
    if staging is not None:
        _validate_staging(staging, journal.planned)
    records: list[tuple[str, Path | None]] = []
    for name in _committed_targets(dest, journal):
        target = _removable_directory(dest, name)
        if target is not None:
            _validate_record(target, complete=True)
        records.append((name, target))
    return records, staging


def _validate_completion(dest: Path, journal: Journal) -> Path | None:
    """The one path a completion removes — the staging directory, empty once
    every record was renamed out of it — proven removable."""
    staging = _removable_directory(dest, journal.staging)
    if staging is not None and (left := sorted(_entry_modes(staging))):
        raise PublicationRecoveryError(
            f"{staging} still holds {', '.join(map(repr, left))} though the journal records every"
            " record as committed; refusing to remove it"
        )
    return staging


def rollback_journal(dest: Path, journal: Journal) -> list[str]:
    """Undo a journaled transaction: remove the committed record directories
    (plus the one whose rename completed before the journal could say so),
    the staging directory, then the journal.  Only names the journal lists
    are ever touched, each proven an immediate real child of *dest* holding
    only what the transaction copies; a target that fails the proof aborts
    before anything is removed."""
    dest = Path(dest)
    records, staging = _validate_rollback(dest, journal)
    removed: list[str] = []
    for name, target in records:
        if target is not None:
            shutil.rmtree(target)
        removed.append(name)
    if staging is not None:
        shutil.rmtree(staging)
    os.unlink(journal_path(dest))
    return removed


def _complete_journal(dest: Path, journal: Journal) -> None:
    """Every record is in place: drop the (empty) staging directory and the
    journal — the staging directory proven removable first."""
    staging = _validate_completion(dest, journal)
    if staging is not None:
        shutil.rmtree(staging)
    os.unlink(journal_path(dest))


class PublicationTransaction:
    """One publication: ``begin`` → ``stage`` → ``commit`` → ``finish``, or
    ``rollback``.  :func:`stage_publication` drives the steps in order under
    the destination lock (:class:`PublicationLock`); tests drive them one at
    a time to stand in for an invocation that died between steps — whose
    lock the kernel dropped and whose journal the next invocation recovers."""

    def __init__(self, plan: PublicationPlan) -> None:
        self.dest = Path(plan.dest)
        self.results_repo = Path(plan.results_repo)
        self.runs = list(plan.to_stage)
        self.journal_path = journal_path(self.dest)
        self.journal: Journal | None = None
        self.staging: Path | None = None
        self.written: list[Path] = []

    # -- steps ---------------------------------------------------------------

    def begin(self) -> None:
        """Create the journal (exclusively — a second transaction into the
        same destination refuses) and the private staging directory, or
        leave nothing behind.  Once the journal exists, every failure —
        duplicating its descriptor, writing it, closing either descriptor,
        creating staging — is an initialization failure: what this attempt
        created is removed (staging, then the journal, proven to be this
        attempt's very file — :meth:`_journal_is_mine`) and
        :class:`PublicationRefused` is raised with the cause chained; a
        removal that itself fails keeps the evidence and raises
        :class:`PublicationRecoveryError` saying exactly what is left and
        what to do about it.  Every descriptor is closed on every path."""
        try:
            self.dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PublicationRefused(f"cannot create the destination {self.dest}: {exc.strerror or exc}") from exc
        for run in self.runs:
            if not _safe_record_name(run.run_id):
                raise PublicationRefused(f"run id {run.run_id!r} is not a safe directory name")
        staging_name = f"{STAGING_PREFIX}{secrets.token_hex(4)}"
        staging = self.dest / staging_name
        journal = Journal(staging=staging_name, planned=[run.run_id for run in self.runs])
        payload = (json.dumps(journal.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        writer: int | None = self._create_journal()
        # The journal exists from here on.  ``writer`` writes it and is
        # closed as soon as the payload is down — a deferred write error
        # surfaces there.  ``proof``, a duplicate, outlives that close so a
        # failure anywhere below can still show that what the path names is
        # this attempt's file.  A variable is cleared the moment its
        # descriptor's ownership passes on or its close is attempted, so no
        # descriptor is closed twice; whichever is still open reaches
        # _abandon_begin as the proof and is closed on the way out.
        proof: int | None = None
        mine: os.stat_result | None = None
        staged = False
        try:
            mine = os.fstat(writer)
            proof = os.dup(writer)
            fd, writer = writer, None
            _write_whole(fd, payload)
            os.mkdir(staging)
            staged = True
            fd, proof = proof, None
            os.close(fd)
        except OSError as exc:
            try:
                self._abandon_begin(
                    exc,
                    journal=journal,
                    payload=payload,
                    mine=mine,
                    proof=proof if proof is not None else writer,
                    staging=staging if staged else None,
                )
            finally:
                # Whatever is still open has nothing left to report: the
                # writer's own close is a guarded step above, and by now the
                # journal is removed, or kept and named in the error in flight.
                for fd in (writer, proof):
                    if fd is not None:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
        self.journal = journal
        self.staging = staging

    def _create_journal(self) -> int:
        """The journal, created exclusively; returns its write descriptor.
        When this refuses, nothing was created."""
        try:
            return os.open(self.journal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o644)
        except FileExistsError:
            raise PublicationRefused(
                f"{self.journal_path} exists: another publication into {self.dest} is in"
                " flight or was interrupted — finish its recovery first"
            ) from None
        except OSError as exc:
            raise PublicationRefused(
                f"cannot begin a publication into {self.dest}: the journal {self.journal_path}"
                f" could not be created ({exc.strerror or exc}); nothing was created"
            ) from exc

    def _abandon_begin(
        self,
        exc: OSError,
        *,
        journal: Journal,
        payload: bytes,
        mine: os.stat_result | None,
        proof: int | None,
        staging: Path | None,
    ) -> NoReturn:
        """Beginning failed after the journal was created: remove what this
        attempt made and refuse, or — when even that fails — keep the
        evidence and say so.  *staging* is the directory this attempt
        created (``None`` when it never got that far) and goes first; the
        journal goes only once proven to be this attempt's very file
        (:meth:`_journal_is_mine`).  *mine* is the created file's identity
        and *proof* a still-open descriptor of it, ``None`` when closing the
        last one was the failure."""
        path = self.journal_path
        why = f"{type(exc).__name__}: {exc.strerror or exc}"
        failed = f"beginning the publication into {self.dest} failed ({why}) AND"
        kept = (
            f" — {path} is KEPT. It plans {', '.join(journal.planned)} into {journal.staging}"
            " with nothing committed: if it parses, the next invocation recovers it by removing"
            " only that staging directory (if present) and the journal; if it does not parse"
            " (the write was interrupted), confirm it names nothing you want kept and delete it"
            f" by hand. No publication proceeds into {self.dest} until then"
        )
        if staging is not None:
            try:
                os.rmdir(staging)
            except FileNotFoundError:
                pass
            except OSError as rmdir_exc:
                raise PublicationRecoveryError(
                    f"{failed} the staging directory it had created could not be removed"
                    f" ({rmdir_exc.strerror or rmdir_exc}): {staging} is kept{kept}"
                ) from exc
        try:
            now = os.lstat(path)
        except FileNotFoundError:
            now = None
        except OSError as lstat_exc:
            raise PublicationRecoveryError(
                f"{failed} the journal it had created cannot be inspected ({lstat_exc.strerror or lstat_exc}){kept}"
            ) from exc
        if now is not None:
            try:
                is_mine = self._journal_is_mine(now, mine=mine, proof=proof, payload=payload)
            except OSError as probe_exc:
                raise PublicationRecoveryError(
                    f"{failed} {path} cannot be proven to be the file this transaction created"
                    f" ({probe_exc.strerror or probe_exc}); refusing to remove it — inspect it by hand;"
                    f" no publication proceeds into {self.dest} until it is resolved"
                ) from exc
            if not is_mine:
                raise PublicationRecoveryError(
                    f"{failed} {path} is no longer the file this transaction created; refusing to"
                    f" remove it — inspect it by hand; no publication proceeds into {self.dest} until"
                    " it is resolved"
                ) from exc
            try:
                os.unlink(path)
            except OSError as unlink_exc:
                raise PublicationRecoveryError(
                    f"{failed} the journal it had created could not be removed ({unlink_exc.strerror or unlink_exc}){kept}"
                ) from exc
        raise PublicationRefused(
            f"cannot begin a publication into {self.dest}: {why}; the journal this attempt had"
            " created is gone and nothing else was created"
        ) from exc

    def _journal_is_mine(self, now: os.stat_result, *, mine: os.stat_result | None, proof: int | None, payload: bytes) -> bool:
        """Whether the entry at the journal's path (*now*, by ``lstat``) is
        the very file this attempt created: a regular file with the created
        file's device and inode (*mine*).  While a descriptor of the created
        file is still open (*proof*), that file's own link count settles it —
        an inode the filesystem reused for a replacement is caught because
        the created file's count has dropped to zero.  When no descriptor is
        open any more (closing the last one was the failure), the entry must
        read back, through a no-follow descriptor of that same inode, as
        exactly the bytes this attempt wrote: the one content a file at that
        path can have and still be this attempt's, so removing an identical
        replacement would lose nothing."""
        if mine is None:
            if proof is None:
                return False
            mine = os.fstat(proof)
        if not stat.S_ISREG(now.st_mode) or (now.st_dev, now.st_ino) != (mine.st_dev, mine.st_ino):
            return False
        if proof is not None:
            return os.fstat(proof).st_nlink > 0
        fd = os.open(self.journal_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            here = os.fstat(fd)
            if not stat.S_ISREG(here.st_mode) or (here.st_dev, here.st_ino) != (mine.st_dev, mine.st_ino):
                return False
            return _read_whole(fd, len(payload) + 1) == payload
        finally:
            os.close(fd)

    def stage(self) -> None:
        """Copy every record into staging, then re-read the copies: each must
        be byte identical to its source and re-prove as the same Run Record.
        The source is re-proven through every ancestor immediately before
        its copy (:func:`source_record_dir`), so a record swapped for a link
        after planning is refused and the transaction rolled back."""
        assert self.staging is not None
        for run in self.runs:
            source_dir = source_record_dir(self.results_repo, run.run_id)
            if source_dir != run.source_dir:
                raise PublicationRefused(
                    f"{run.run_id}: the record moved since planning (from {run.source_dir} to"
                    f" {source_dir}); refusing to publish it"
                )
            target_dir = self.staging / run.run_id
            target_dir.mkdir()
            for name in RECORD_FILES:
                _copy_regular_file(source_dir / name, target_dir / name)
        for run in self.runs:
            target_dir = self.staging / run.run_id
            for name in RECORD_FILES:
                if not _same_bytes(run.source_dir / name, target_dir / name):
                    raise PublicationRefused(
                        f"{run.run_id}: the staged copy of {name} does not match its source"
                        " byte for byte"
                    )
            try:
                staged = RunRecord.from_dicts(
                    json.loads((target_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")),
                    json.loads((target_dir / SCORES_FILENAME).read_text(encoding="utf-8")),
                )
            except (OSError, ValueError, ResultsRepoError) as exc:
                raise PublicationRefused(f"{run.run_id}: the staged copy does not re-prove: {exc}") from exc
            if staged.run_id != run.run_id or staged.candidate.to_dict() != run.record.candidate.to_dict():
                raise PublicationRefused(f"{run.run_id}: the staged copy re-proves as a different record")

    def commit(self) -> None:
        for run in self.runs:
            self.commit_one(run)

    def commit_one(self, run: PlannedRun) -> None:
        """Rename one staged record into place, journaling the step before
        and after so an interruption anywhere is recoverable."""
        assert self.journal is not None and self.staging is not None
        if run.dest_dir.exists() or run.dest_dir.is_symlink():
            raise PublicationRefused(
                f"{run.dest_dir} appeared while publishing — a published record is never"
                " overwritten"
            )
        self.journal.committing = run.run_id
        _write_journal(self.journal_path, self.journal)
        os.rename(self.staging / run.run_id, run.dest_dir)
        self.journal.committed.append(run.run_id)
        self.journal.committing = None
        _write_journal(self.journal_path, self.journal)
        self.written.extend(run.dest_dir / name for name in RECORD_FILES)

    def finish(self) -> None:
        """Every record is in place: drop the (empty) staging directory and
        the journal."""
        assert self.journal is not None and self.staging is not None
        if not self.journal.complete:
            raise PublicationRecoveryError("finish called on an incomplete transaction")
        _complete_journal(self.dest, self.journal)

    def rollback(self) -> list[str]:
        """Remove every final directory this transaction created (and only
        those), the staging directory, and the journal.  Returns the record
        names removed."""
        assert self.journal is not None
        return rollback_journal(self.dest, self.journal)


@dataclass(frozen=True)
class RecoveryReport:
    """What :func:`recover_publication` did — or, from the read-only
    :func:`inspect_publication`, what it would do — about an interrupted
    transaction."""

    action: str  # "rolled-back" | "completed"
    records: tuple[str, ...]
    performed: bool = True

    def describe(self) -> str:
        names = ", ".join(self.records)
        if self.performed:
            if self.action == "completed":
                return (
                    "RECOVERED an interrupted publication that had already committed every record"
                    f" ({names}); cleaned up its staging directory and journal"
                )
            return (
                "RECOVERED an interrupted publication by rolling it back: removed"
                f" {names or 'no record directory'} (only directories that transaction created;"
                " pre-existing records untouched)"
            )
        if self.action == "completed":
            return (
                "RECOVERY REQUIRED: an interrupted publication had already committed every record"
                f" ({names}); running without --dry-run would remove only its staging directory"
                " and journal"
            )
        return (
            "RECOVERY REQUIRED: an interrupted publication would be rolled back; running without"
            f" --dry-run would remove {names or 'no record directory'} (only directories that"
            " transaction created; pre-existing records untouched), its staging directory and"
            " its journal"
        )


def recover_publication(dest: Path) -> RecoveryReport | None:
    """Finish an interrupted transaction under *dest* from its journal:
    roll it back, or complete it when every planned record was already
    committed.  ``None`` when there is nothing to recover.  Raises
    :class:`PublicationRecoveryError` — with the destination unchanged —
    when the journal is not a real regular file (a symlink, dangling or not,
    is never followed), is unreadable, malformed or names anything that is
    not a plain immediate child of *dest*, and when the rollback itself
    fails (the journal then stays for the operator).  Runs under the
    destination's exclusive lock; a transaction in flight there raises
    :class:`PublicationLockedError` and nothing is read."""
    dest = Path(dest)
    if not os.path.exists(dest):
        return None
    path = journal_path(dest)
    with PublicationLock(dest):
        journal = _read_journal(path)
        if journal is None:
            return None
        try:
            if journal.complete:
                _complete_journal(dest, journal)
                return RecoveryReport(action="completed", records=tuple(journal.committed))
            removed = rollback_journal(dest, journal)
        except OSError as exc:
            raise PublicationRecoveryError(
                f"recovery of the interrupted publication under {dest} FAILED: {exc} — the"
                f" journal {path} is kept; inspect the directories it names, fix the"
                " problem, and run again; no publication proceeds until recovery succeeds"
            ) from exc
        return RecoveryReport(action="rolled-back", records=tuple(removed))


def inspect_publication(dest: Path) -> RecoveryReport | None:
    """What :func:`recover_publication` would do under *dest*, without
    changing anything on disk: ``None`` when no journal exists, otherwise a
    report with ``performed=False``.  A journal that recovery would refuse
    raises :class:`PublicationRecoveryError` here too.  Runs under a shared
    hold of the destination lock: a transaction in flight raises
    :class:`PublicationLockedError` instead of being reported as interrupted."""
    dest = Path(dest)
    if not os.path.exists(dest):
        return None
    with PublicationLock(dest, shared=True):
        journal = _read_journal(journal_path(dest))
        if journal is None:
            return None
        if journal.complete:
            _validate_completion(dest, journal)
            return RecoveryReport(action="completed", records=tuple(journal.committed), performed=False)
        records, _staging = _validate_rollback(dest, journal)
        return RecoveryReport(action="rolled-back", records=tuple(name for name, _ in records), performed=False)


def stage_publication(plan: PublicationPlan) -> list[Path]:
    """Publish the records of a refusal-free plan transactionally; return the
    files now in place.  Raises :class:`PublicationRefused` (nothing new
    published) on a refusal or a rolled-back failure, and
    :class:`PublicationRecoveryError` when a rollback itself fails.  Holds
    the destination lock from ``begin`` through ``finish`` or ``rollback``;
    a transaction already in flight there raises
    :class:`PublicationLockedError` before anything is created."""
    if plan.refusals:
        raise PublicationRefused("refusals:\n  " + "\n  ".join(plan.refusals))
    if not plan.to_stage:
        return []
    with PublicationLock(plan.dest) as lock:
        tx = PublicationTransaction(plan)
        tx.begin()
        try:
            tx.stage()
            tx.commit()
            lock.keep_dest()
        except BaseException as exc:
            try:
                removed = tx.rollback()
            except (OSError, PublicationRecoveryError) as rollback_exc:
                raise PublicationRecoveryError(
                    f"publication failed ({type(exc).__name__}: {exc}) AND its rollback failed"
                    f" ({rollback_exc}) — {tx.journal_path} is kept; inspect the directories it"
                    " names, fix the problem, and run again; no publication proceeds until"
                    " recovery succeeds"
                ) from exc
            if isinstance(exc, Exception):
                raise PublicationRefused(
                    f"publication failed and was rolled back (removed"
                    f" {', '.join(removed) or 'nothing'}; pre-existing records untouched):"
                    f" {type(exc).__name__}: {exc}"
                ) from exc
            raise
        try:
            tx.finish()
        except (OSError, PublicationRecoveryError) as exc:
            raise PublicationRecoveryError(
                f"every record was committed, but finishing the publication into {plan.dest}"
                f" failed ({exc}) — {tx.journal_path} is kept and records the transaction as"
                " complete, so the next invocation finishes it (removing only its empty staging"
                " directory and the journal); the records are in place: review and commit them"
                " once that has run"
            ) from exc
        return tx.written


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_plan(plan: PublicationPlan, *, dry_run: bool) -> str:
    """The per-run verdicts (and, for a dry run, the files that would be
    written).  The files actually written are reported by
    :func:`format_committed` after the transaction commits."""
    lines = [f"destination: {plan.dest}"]
    for run in plan.runs:
        trace = run.traceability
        where = trace.candidate_dir.name if trace else "UNTRACEABLE"
        status = "already published (identical)" if run.already_staged else ("would publish" if dry_run else "publish")
        lines.append(
            f"  {run.run_id}: candidate {where}, benchmark {run.record.benchmark}, mode"
            f" {run.record.mode}, leaderboard_valid={str(run.record.leaderboard_valid).lower()}"
            f" — {status}"
        )
        for reason in run.warnings:
            lines.append(f"    WARNING: {reason}")
        for reason in run.refusals:
            lines.append(f"    REFUSED: {reason}")
    if plan.refusals:
        lines.append("nothing published: resolve every REFUSED line above")
    elif dry_run:
        for run in plan.to_stage:
            for name in RECORD_FILES:
                lines.append(f"  + {run.dest_dir / name}")
        lines.append("dry run: nothing written")
    return "\n".join(lines)


def format_committed(written: list[Path]) -> str:
    lines = [f"  A {path}" for path in written]
    lines.append(
        "this script ran no git command: review the published files and commit them —"
        " the commit is the approval stamp"
        if written
        else "nothing to publish: every record was already published (identical)"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Discovery of published results — by manifest, never by path convention
# ---------------------------------------------------------------------------


def iter_published_records(root: Path = DEFAULT_PUBLISHED_DIR) -> Iterator[tuple[Path, RunRecord]]:
    """Every published record under *root*, wherever the operator placed it:
    a directory is a published run iff it holds ``manifest.json`` beside
    ``scores.json`` and the pair re-proves as a record whose ``run_id`` is
    the directory's name.  Malformed pairs raise; directory layout above the
    record carries no meaning.  Dot-prefixed directories (a transaction's
    staging) are never records.  Only what the tree itself holds counts: a
    symlinked directory, or a symlink or special file under a record file's
    name, raises and is never followed — a published record is a real
    in-tree directory holding regular files."""
    root = Path(root)
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        directory = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        modes = {name: os.lstat(directory / name).st_mode for name in (*dirnames, *filenames)}
        for name in sorted(modes):
            if stat.S_ISLNK(modes[name]) and (name in dirnames or name in RECORD_FILES):
                raise ResultsRepoError(
                    f"{directory / name}: a symlink — a published record is a real in-tree"
                    " directory holding regular files; refusing to follow it"
                )
        if MANIFEST_FILENAME not in modes:
            continue
        if SCORES_FILENAME not in modes:
            raise ResultsRepoError(f"{directory}: {MANIFEST_FILENAME} without {SCORES_FILENAME}")
        for name in RECORD_FILES:
            if not stat.S_ISREG(modes[name]):
                raise ResultsRepoError(
                    f"{directory / name} is {_file_kind(modes[name])}, not a regular file — a"
                    " published record holds regular files only; refusing to read through it"
                )
        record = RunRecord.from_dicts(
            json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8")),
            json.loads((directory / SCORES_FILENAME).read_text(encoding="utf-8")),
        )
        if record.run_id != directory.name:
            raise ResultsRepoError(
                f"{directory}: manifest run_id {record.run_id!r} does not match the directory name"
            )
        yield directory, record


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Publish run records into published/ transactionally (traceability = hard"
            " refusal, validity = warning; never commits)."
        )
    )
    parser.add_argument("run_ids", nargs="+", metavar="RUN_ID")
    parser.add_argument(
        "--results-repo", type=Path, default=None,
        help=f"the private Results Repo clone (or ${RESULTS_REPO_ENV})",
    )
    parser.add_argument("--dest", type=Path, required=True, help="destination, e.g. published/<subdir>")
    parser.add_argument("--candidates-dir", type=Path, default=DEFAULT_CANDIDATES_DIR)
    parser.add_argument("--allow-invalid", action="store_true", help="publish runs with leaderboard_valid: false")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="check everything, write nothing (a pending journal is reported, never recovered)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    results_repo = resolve_results_repo(args.results_repo)
    if results_repo is None:
        print(f"REFUSED: pass --results-repo or set ${RESULTS_REPO_ENV}", file=sys.stderr)
        return 1
    try:
        # One hold of the destination lock spans the whole lifecycle: a
        # shared one for the read-only dry run, an exclusive one for
        # recovery, planning, staging, commit and finish.
        if args.dry_run:
            with PublicationLock(args.dest, shared=True):
                return _dry_run(args, results_repo)
        with PublicationLock(args.dest):
            return _publish(args, results_repo)
    except PublicationRecoveryError as exc:
        print(f"RECOVERY FAILED: {exc}", file=sys.stderr)
        return 2
    except PublicationCleanupError as exc:
        if exc.refusal is not None:
            print(f"REFUSED: {exc.refusal}", file=sys.stderr)
        print(f"CLEANUP FAILED: {exc}", file=sys.stderr)
        return 2
    except PublicationLockedError as exc:
        print(f"REFUSED: {exc}" + (" — the dry run changed nothing" if args.dry_run else ""), file=sys.stderr)
        return 1
    except PublicationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


def _dry_run(args: argparse.Namespace, results_repo: Path) -> int:
    """Strictly read-only: a pending journal is inspected and reported,
    never acted on."""
    try:
        pending = inspect_publication(args.dest)
    except PublicationRecoveryError as exc:
        print(f"RECOVERY REQUIRED but would FAIL: {exc} — the dry run changed nothing", file=sys.stderr)
        return 2
    if pending is not None:
        print(pending.describe())
        print(
            f"REFUSED: recovery is required under {args.dest} before new work can be"
            " planned; the dry run changed nothing — run again without --dry-run to"
            " perform it",
            file=sys.stderr,
        )
        return 1
    plan = plan_publication(
        args.run_ids,
        results_repo=results_repo,
        dest=args.dest,
        candidates_dir=args.candidates_dir,
        allow_invalid=args.allow_invalid,
    )
    print(format_plan(plan, dry_run=True))
    return 1 if plan.refusals else 0


def _publish(args: argparse.Namespace, results_repo: Path) -> int:
    recovered = recover_publication(args.dest)
    if recovered is not None:
        print(recovered.describe())
    plan = plan_publication(
        args.run_ids,
        results_repo=results_repo,
        dest=args.dest,
        candidates_dir=args.candidates_dir,
        allow_invalid=args.allow_invalid,
    )
    print(format_plan(plan, dry_run=False))
    if plan.refusals:
        return 1
    written = stage_publication(plan)
    print(format_committed(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
