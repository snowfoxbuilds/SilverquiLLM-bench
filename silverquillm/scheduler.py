"""The file-backed batch queue and its single-writer scheduler (#39 §5, #66 Part B).

The substrate learns nothing about batches: a *batch* is one TOML file the
operator authors under ``batches/`` — **desired state** — and the scheduler
is one long-running bench-side process that turns it into Contract Runs,
serially, through the same bundle run path ``silverquillm run --candidate``
uses.  Everything the scheduler observes goes into its own state file beside
the queue; a batch file is never written by the scheduler.

Batch file, ``batches/<id>.toml``::

    not_before = 2026-09-04T02:00:00Z      # optional; RFC 3339 with an offset

    [[runs]]
    candidate = "candidates/vanilla-claude--4e8b75b6"   # a path, or a candidates/ entry
    mode = "basic"
    benchmark = "smoke"
    budget_seconds = 14400

Semantics the scheduler enforces:

- **Scan order / serial execution.**  Batch files are scanned in name order
  and run specs consumed in file order; one run executes at a time.  At every
  step the scheduler takes the first due batch (``not_before`` passed, or
  absent) that still has an unconsumed entry — so batches execute serially in
  name order, and a batch whose ``not_before`` lies ahead is simply skipped
  until it is due.
- **Re-read before each run.**  The batch file is re-read before every
  not-yet-started run.  The Nth started run is whatever the file's Nth
  ``[[runs]]`` entry is *at that moment*: edits to entries already started
  change nothing (the state records what actually ran), edits to later
  entries — including appended ones — take effect.  A file that shrinks below
  the number of runs already started simply has no more work.
- **Identity at run start.**  The candidate is resolved and its identity
  recomputed (:func:`silverquillm.candidate.load_candidate_bundle`) when the
  run starts, never at authoring time; the state records that identity, and
  the run's RunRecord carries the same recomputed identity.  Editing a
  candidate between scheduling and execution is legal: results record what
  actually ran.
- **Failure continues the batch** (a #66 decision: #39 gives no abort-on-fail
  rule).  A run that fails — refused candidate, unknown mode or benchmark, a
  driver failure, an executor exception — is marked ``failed`` with its
  reason and the scheduler moves on to the next entry.  A batch is a
  best-effort serial list, not a transaction.
- **Malformed batch files are skipped loudly**, reported once per file
  version to the scheduler log, and surfaced by ``silverquillm queue ls``.
- **Single writer.**  ``batches/.scheduler.lock`` is held with ``flock`` for
  the scheduler's whole life; a second instance refuses to start and names
  the holder.  The kernel drops the lock with the process, so a crash never
  leaves a stale lock.

Two kinds of scheduler-owned files sit beside the queue:

- **Committed observed state**, ``batches/state/<id>.json`` — portable and
  tracked in git (the operator commits checkpoints; the scheduler never runs
  git).  Schema-versioned, one entry per *started* run (index, the spec as
  consumed, ``running`` → ``done`` / ``failed``, run id, the identity and
  candidate hash resolved at run start, portable timestamps, outcome summary
  and a sanitized error), written atomically after every transition.  The
  number of entries is the batch's cursor.  It carries **no** host-local
  detail: no absolute path, no home directory, no pid or hostname, no
  container data, no environment value, no traceback.  The consumed spec
  keeps a relative candidate reference verbatim and records an absolute one
  as ``<external-candidate>/<basename>`` (:func:`portable_spec`): the
  recorded identity is the authoritative account of what ran, and a pending
  entry always resolves from the batch file, never from this copy.  Every
  summary and error passes the scheduler's redaction first — the exact
  values bound to the bundle's declared secret slots in the effective
  environment, one of those slots used as an assignment key with any
  non-empty value (no length or character-set rule; a bare value to its
  line end, a quoted one to its closing quote), every generic credential
  shape (:func:`silverquillm.candidate.redact_credentials`), then
  host-local roots replaced by placeholders.  **Every log line passes the
  same redaction** on its one way to the sink (:meth:`Scheduler._log`): the
  generic shapes and root placeholders always — blocked and malformed
  warnings, acknowledgements, recovery, the serve line (which therefore
  names the queue as ``<batches>``, never by absolute path) — and, once a
  run has resolved its bundle, the bound values of its declared slots too:
  ``STARTED``, ``DONE``/``FAILED``, executor errors and interruptions.
  Identity fields (run id, worker type, candidate hash) are recorded
  verbatim in the state; in the log they are subject to the same value
  redaction as any other text.
- **Ignored runtime metadata**, ``batches/runtime/<id>.json`` — host-local,
  gitignored, present only while a run of that batch is active: the batch,
  index and run id of the running entry, the scheduler pid and hostname.
  Removed after the run's terminal transition.  It names no container: the
  one container a recovery may touch is derived from the committed entry the
  record binds to (:func:`silverquillm.contract.container_name` of that
  entry's run id), never read from the record.

**Missing state is fail-closed.**  A batch file whose state file is absent
is *blocked*: nothing from it runs, and the scheduler warns — once per file
version — that starting it from entry zero may replay work already completed
elsewhere and incur model and runtime costs.  The operator restores the
committed checkpoint, or acknowledges the replay for that one batch with
``--replay-without-state <id>``, which creates the empty state and lets the
batch start from run zero.  There is no global acknowledgement.  Malformed or
future-version state blocks the batch the same way.  Batch ids are one-shot
identifiers: a state file, once committed, is the record of what ran under
that id, so an id is never reused for an unrelated batch.

**Abandoned runs are reconciled before anything else runs.**  A run left
``running`` by a scheduler that died is reconciled at startup, under the
lock, before any new work.  First every batch's runtime record is bound to
the committed state — batch, index and run id must all equal the running
entry's (:func:`bind_runtime`); a record that is unreadable, malformed or
names another run stops the scheduler before any container operation.  Then,
on the same host (the record's hostname is this one) the container
``container_name(<that entry's run id>)`` is force-removed and its absence
confirmed, and the run is marked ``failed``; if the container cannot be
removed or its removal cannot be confirmed, the scheduler stops with a
diagnostic and executes nothing.  Without local runtime metadata — the state
was committed on another host — the run cannot be reconciled here: the
scheduler stops until the operator confirms the cleanup with
``--acknowledge-cleanup <id>``.  That acknowledgement is for a replacement
host only: it is refused while valid same-host runtime metadata exists (the
run is reconciled here instead), and it fails closed — the runtime file
kept — when the metadata is unreadable or does not bind to the recorded run.
One scheduler and one run container per queue, always.

Public API
----------
:class:`Scheduler` (``run_next`` / ``run_until_idle`` / ``serve``),
:class:`SchedulerLock` + :func:`lock_status`, :func:`load_batch`,
:func:`list_batch_files`, :func:`load_state` / :func:`save_state`,
:func:`inspect_batch` (the blocked / runnable classification the views
share), the runtime record helpers, :class:`DockerContainerRuntime` +
:func:`reconcile_container`, :func:`resolve_candidate_ref`,
:func:`contract_run_executor`, the :class:`RunSpec` / :class:`Batch` /
:class:`BatchState` / :class:`RunState` records, and :class:`RunOutcome` —
the executor's result shape.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import socket
import subprocess
import tempfile
import threading
import time
import tomllib
import traceback
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, Self

from silverquillm.candidate import CandidateBundle, load_candidate_bundle, redact_credentials
from silverquillm.contract import RUNS_DIRNAME, candidate_label, container_name, new_run_name
from silverquillm.jobdir import BenchmarkRef, load_benchmark
from silverquillm.modes import BenchmarkMode, get_mode
from silverquillm.results_repo import candidate_hash, candidate_hash8

__all__ = [
    "BATCHES_DIRNAME",
    "BATCH_SUFFIX",
    "BLOCK_ABANDONED_RUN",
    "BLOCK_MISSING_STATE",
    "BLOCK_UNREADABLE_STATE",
    "DEFAULT_POLL_SECONDS",
    "EXTERNAL_CANDIDATE_PREFIX",
    "FAILURE_ABANDONED",
    "FAILURE_INTERRUPTED",
    "FAILURE_SCHEDULER",
    "FAILURE_UNRESOLVABLE",
    "LOCK_FILENAME",
    "RUNTIME_DIRNAME",
    "RUN_DONE",
    "RUN_FAILED",
    "RUN_PENDING",
    "RUN_RUNNING",
    "RUN_STATES",
    "STATE_DIRNAME",
    "STATE_SCHEMA_VERSION",
    "AcknowledgementError",
    "Batch",
    "BatchBlock",
    "BatchError",
    "BatchState",
    "ContainerRuntime",
    "DockerContainerRuntime",
    "Executor",
    "LockStatus",
    "ReconciliationError",
    "ResolvedRun",
    "RunOutcome",
    "RunSpec",
    "RunState",
    "RuntimeRecord",
    "Scheduler",
    "SchedulerError",
    "SchedulerLock",
    "SchedulerLockedError",
    "SchedulerStopped",
    "StateError",
    "batch_id_of",
    "bind_runtime",
    "clear_runtime",
    "contract_run_executor",
    "inspect_batch",
    "list_batch_files",
    "list_runtime_files",
    "load_batch",
    "load_runtime",
    "load_state",
    "lock_status",
    "parse_batch",
    "portable_spec",
    "reconcile_container",
    "resolve_candidate_ref",
    "running_entry",
    "runtime_path",
    "save_runtime",
    "save_state",
    "state_path",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent

BATCHES_DIRNAME = "batches"
STATE_DIRNAME = "state"
RUNTIME_DIRNAME = "runtime"
LOCK_FILENAME = ".scheduler.lock"
BATCH_SUFFIX = ".toml"
STATE_SCHEMA_VERSION = 1
RUNTIME_SCHEMA_VERSION = 1
DEFAULT_POLL_SECONDS = 30

RUN_PENDING = "pending"
RUN_RUNNING = "running"
RUN_DONE = "done"
RUN_FAILED = "failed"
RUN_STATES = (RUN_PENDING, RUN_RUNNING, RUN_DONE, RUN_FAILED)

FAILURE_UNRESOLVABLE = "unresolvable"
FAILURE_SCHEDULER = "scheduler"
FAILURE_INTERRUPTED = "interrupted"
FAILURE_ABANDONED = "abandoned"

BLOCK_MISSING_STATE = "missing-state"
BLOCK_UNREADABLE_STATE = "unreadable-state"
BLOCK_ABANDONED_RUN = "abandoned-run"

_RUN_SPEC_KEYS = frozenset({"candidate", "mode", "benchmark", "budget_seconds"})
_BATCH_KEYS = frozenset({"not_before", "runs"})
_STATE_KEYS = frozenset({"schema_version", "batch", "batch_file", "updated_at", "runs"})
_RUN_STATE_KEYS = frozenset({
    "index", "spec", "state", "started_at", "finished_at", "run_id", "candidate_hash",
    "hash8", "identity", "resolved_at", "ok", "failure_class", "summary", "error",
})
_RUNTIME_KEYS = frozenset({"schema_version", "batch", "index", "run_id", "pid", "hostname", "started_at"})
#: How the committed state records an absolute candidate reference: a label
#: that is not a path, followed by the reference's basename.
EXTERNAL_CANDIDATE_PREFIX = "<external-candidate>/"
#: A sanitized error summary is one line, capped: never a traceback.
_ERROR_MAX_CHARS = 600


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


class SchedulerError(Exception):
    """A scheduler-side failure (a run spec that cannot be resolved, a bad ref)."""


class BatchError(Exception):
    """A batch file is malformed; the scheduler skips it loudly."""


class StateError(Exception):
    """A scheduler state file is unreadable, malformed, or of another schema
    version — the batch is blocked (fail closed)."""


class SchedulerLockedError(Exception):
    """Another scheduler holds ``batches/.scheduler.lock``."""


class ReconciliationError(SchedulerError):
    """An abandoned run cannot be reconciled (its container could not be
    removed or confirmed gone, or it belongs to another host): the scheduler
    stops and executes nothing."""


class AcknowledgementError(SchedulerError):
    """A ``--replay-without-state`` / ``--acknowledge-cleanup`` names a batch
    it does not apply to; the scheduler refuses to start."""


class SchedulerStopped(BaseException):
    """Raised in the main thread when SIGTERM arrives, so the run in flight
    is interrupted like a Ctrl-C and the scheduler unwinds cleanly."""


# ---------------------------------------------------------------------------
# Batch files (desired state — read-only to the scheduler)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunSpec:
    """One ``[[runs]]`` entry: the run spec (candidate + mode + benchmark + budget)."""

    candidate: str
    mode: str
    benchmark: str
    budget_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "mode": self.mode,
            "benchmark": self.benchmark,
            "budget_seconds": self.budget_seconds,
        }

    @classmethod
    def from_mapping(cls, data: Any, *, context: str) -> RunSpec:
        if not isinstance(data, Mapping):
            raise BatchError(f"{context}: a [[runs]] entry must be a table")
        unknown = sorted(set(data) - _RUN_SPEC_KEYS)
        if unknown:
            raise BatchError(f"{context}: unknown key(s) {', '.join(unknown)} (allowed: {', '.join(sorted(_RUN_SPEC_KEYS))})")
        missing = sorted(_RUN_SPEC_KEYS - set(data))
        if missing:
            raise BatchError(f"{context}: missing key(s) {', '.join(missing)}")
        for key in ("candidate", "mode", "benchmark"):
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise BatchError(f"{context}: {key} must be a non-empty string")
        budget = data["budget_seconds"]
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise BatchError(f"{context}: budget_seconds must be a positive integer")
        return cls(
            candidate=data["candidate"],
            mode=data["mode"],
            benchmark=data["benchmark"],
            budget_seconds=budget,
        )


@dataclass(frozen=True)
class Batch:
    """A parsed batch file: its id (the file stem), ``not_before``, and the
    ordered run specs."""

    id: str
    path: Path
    not_before: datetime | None
    runs: tuple[RunSpec, ...]

    def due(self, now: datetime) -> bool:
        return self.not_before is None or now >= self.not_before


def _parse_not_before(value: Any, *, context: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise BatchError(f"{context}: not_before {value!r} is not an RFC 3339 timestamp") from exc
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise BatchError(
                f"{context}: not_before must carry a UTC offset (e.g. 2026-09-04T02:00:00Z)"
                " — a local-time value is ambiguous"
            )
        return value
    raise BatchError(f"{context}: not_before must be an RFC 3339 timestamp, got {value!r}")


def batch_id_of(path: Path) -> str:
    return Path(path).name.removesuffix(BATCH_SUFFIX)


def parse_batch(text: str, *, batch_id: str, path: Path) -> Batch:
    """Parse batch TOML strictly: exactly the documented keys and shapes."""
    context = f"batch {batch_id}"
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BatchError(f"{context}: does not parse as TOML: {exc}") from exc
    unknown = sorted(set(data) - _BATCH_KEYS)
    if unknown:
        raise BatchError(f"{context}: unknown top-level key(s) {', '.join(unknown)} (allowed: not_before, runs)")
    not_before = _parse_not_before(data["not_before"], context=context) if "not_before" in data else None
    runs_raw = data.get("runs", [])
    if not isinstance(runs_raw, list):
        raise BatchError(f"{context}: runs must be an array of [[runs]] tables")
    runs = tuple(
        RunSpec.from_mapping(entry, context=f"{context} [[runs]] #{index}") for index, entry in enumerate(runs_raw)
    )
    return Batch(id=batch_id, path=Path(path), not_before=not_before, runs=runs)


def load_batch(path: Path) -> Batch:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BatchError(f"batch {batch_id_of(path)}: cannot read {path}: {exc}") from exc
    return parse_batch(text, batch_id=batch_id_of(path), path=path)


def list_batch_files(batches_dir: Path) -> list[Path]:
    """Every ``batches/<id>.toml`` (regular files, no dot-prefix), in name order."""
    batches_dir = Path(batches_dir)
    if not batches_dir.is_dir():
        return []
    return sorted(
        p for p in batches_dir.iterdir()
        if p.name.endswith(BATCH_SUFFIX) and not p.name.startswith(".") and p.is_file() and not p.is_symlink()
    )


# ---------------------------------------------------------------------------
# Committed observed state — portable, git-tracked, host-free
# ---------------------------------------------------------------------------


def portable_spec(spec: RunSpec) -> dict[str, Any]:
    """The consumed spec as the committed state records it: a relative
    candidate reference verbatim, an absolute one — a host-local path — as
    ``<external-candidate>/<basename>``.  The recorded identity is the
    authoritative account of what ran; a pending entry always resolves from
    the batch file, never from this copy."""
    data = spec.to_dict()
    if os.path.isabs(spec.candidate):
        data["candidate"] = EXTERNAL_CANDIDATE_PREFIX + (Path(spec.candidate).name or "candidate")
    return data


def _validate_portable_spec(spec: Mapping[str, Any], *, context: str) -> dict[str, Any]:
    unknown = sorted(set(spec) - _RUN_SPEC_KEYS)
    if unknown:
        raise StateError(f"{context}: unknown spec field(s) {', '.join(unknown)}; refusing to interpret it")
    for key in ("candidate", "mode", "benchmark"):
        if key in spec and not isinstance(spec[key], str):
            raise StateError(f"{context}: spec.{key} must be a string")
    if "budget_seconds" in spec and (isinstance(spec["budget_seconds"], bool) or not isinstance(spec["budget_seconds"], int)):
        raise StateError(f"{context}: spec.budget_seconds must be an integer")
    for key, value in spec.items():
        if isinstance(value, str) and os.path.isabs(value):
            raise StateError(
                f"{context}: spec.{key} carries an absolute path — committed state is portable"
                f" and records an absolute candidate reference as {EXTERNAL_CANDIDATE_PREFIX}<basename>"
            )
    return dict(spec)


@dataclass
class RunState:
    """One started run of a batch, as the scheduler observed it — every
    field portable (no path, pid, host, container or environment value;
    the spec as :func:`portable_spec` records it)."""

    index: int
    spec: dict[str, Any]
    state: str
    started_at: str | None = None
    finished_at: str | None = None
    run_id: str | None = None
    candidate_hash: str | None = None
    hash8: str | None = None
    identity: dict[str, Any] | None = None
    resolved_at: str | None = None
    ok: bool | None = None
    failure_class: str | None = None
    summary: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "spec": dict(self.spec),
            "state": self.state,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "run_id": self.run_id,
            "candidate_hash": self.candidate_hash,
            "hash8": self.hash8,
            "identity": dict(self.identity) if self.identity is not None else None,
            "resolved_at": self.resolved_at,
            "ok": self.ok,
            "failure_class": self.failure_class,
            "summary": self.summary,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Any, *, context: str) -> RunState:
        if not isinstance(data, Mapping):
            raise StateError(f"{context}: a run entry must be an object")
        unknown = sorted(set(data) - _RUN_STATE_KEYS)
        if unknown:
            raise StateError(
                f"{context}: unknown run field(s) {', '.join(unknown)} — written by a newer"
                " scheduler, or not a state file; refusing to interpret it"
            )
        try:
            index = data["index"]
            spec = data["spec"]
            state = data["state"]
        except KeyError as exc:
            raise StateError(f"{context}: run entry lacks {exc}") from exc
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise StateError(f"{context}: run index must be a non-negative integer")
        if not isinstance(spec, Mapping):
            raise StateError(f"{context}: run spec must be an object")
        spec = _validate_portable_spec(spec, context=context)
        if state not in RUN_STATES:
            raise StateError(f"{context}: unknown run state {state!r}")
        run_id = data.get("run_id")
        if run_id is not None and (not isinstance(run_id, str) or not run_id):
            raise StateError(f"{context}: run_id must be a non-empty string or null")
        identity = data.get("identity")
        return cls(
            index=index,
            spec=spec,
            state=state,
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            run_id=run_id,
            candidate_hash=data.get("candidate_hash"),
            hash8=data.get("hash8"),
            identity=dict(identity) if isinstance(identity, Mapping) else None,
            resolved_at=data.get("resolved_at"),
            ok=data.get("ok"),
            failure_class=data.get("failure_class"),
            summary=str(data.get("summary") or ""),
            error=data.get("error"),
        )


@dataclass
class BatchState:
    """``batches/state/<id>.json``: every started run of the batch, in order.
    ``batch_file`` is the batch file's *name* (never a path)."""

    batch: str
    batch_file: str = ""
    runs: list[RunState] = field(default_factory=list)
    updated_at: str = ""

    @property
    def consumed(self) -> int:
        """The batch's cursor: how many of its entries have been started."""
        return len(self.runs)

    @property
    def running(self) -> list[RunState]:
        return [run for run in self.runs if run.state == RUN_RUNNING]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "batch": self.batch,
            "batch_file": self.batch_file,
            "updated_at": self.updated_at,
            "runs": [run.to_dict() for run in self.runs],
        }

    @classmethod
    def from_dict(cls, data: Any, *, context: str) -> BatchState:
        if not isinstance(data, Mapping):
            raise StateError(f"{context}: must be a JSON object")
        version = data.get("schema_version")
        if version != STATE_SCHEMA_VERSION:
            raise StateError(
                f"{context}: schema_version {version!r} is not {STATE_SCHEMA_VERSION} —"
                " written by another scheduler version; refusing to interpret it"
            )
        unknown = sorted(set(data) - _STATE_KEYS)
        if unknown:
            raise StateError(f"{context}: unknown field(s) {', '.join(unknown)}; refusing to interpret it")
        runs_raw = data.get("runs", [])
        if not isinstance(runs_raw, list):
            raise StateError(f"{context}: runs must be an array")
        runs = [RunState.from_dict(entry, context=f"{context} run #{i}") for i, entry in enumerate(runs_raw)]
        for i, run in enumerate(runs):
            if run.index != i:
                raise StateError(f"{context}: run entry #{i} carries index {run.index}; entries are the batch cursor")
        return cls(
            batch=str(data.get("batch", "")),
            batch_file=str(data.get("batch_file", "")),
            runs=runs,
            updated_at=str(data.get("updated_at", "")),
        )


def state_path(batches_dir: Path, batch_id: str) -> Path:
    return Path(batches_dir) / STATE_DIRNAME / f"{batch_id}.json"


def load_state(batches_dir: Path, batch_id: str) -> BatchState | None:
    """The batch's committed state; ``None`` when no state file exists (the
    batch is blocked until the operator acknowledges it — see
    :func:`inspect_batch`).  A malformed, unreadable or other-version file is
    a :class:`StateError`."""
    path = state_path(batches_dir, batch_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError(f"{path.name}: {exc}") from exc
    state = BatchState.from_dict(data, context=path.name)
    if state.batch != batch_id:
        raise StateError(f"{path.name}: records batch {state.batch!r}, not {batch_id!r}")
    return state


def save_state(batches_dir: Path, state: BatchState, *, now: datetime | None = None) -> Path:
    """Write the state file atomically (temp file + rename).  Never runs git:
    the operator commits the checkpoint."""
    path = state_path(batches_dir, state.batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = _stamp(now or _now())
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    _write_atomically(path, payload, prefix=f".{state.batch}-")
    return path


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


# ---------------------------------------------------------------------------
# Runtime metadata — host-local, gitignored, present only while a run is active
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeRecord:
    """``batches/runtime/<id>.json``: which committed entry a scheduler on
    this host left running (batch, index, run id) and who ran it (pid,
    hostname).  It names no container — the container a recovery may touch
    is derived from the committed entry the record binds to
    (:func:`bind_runtime`), never read from here."""

    batch: str
    index: int
    run_id: str
    pid: int
    hostname: str
    started_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "batch": self.batch,
            "index": self.index,
            "run_id": self.run_id,
            "pid": self.pid,
            "hostname": self.hostname,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: Any, *, context: str) -> RuntimeRecord:
        """Strict: exactly the documented fields with their documented types
        — a record is bound, never coerced."""
        if not isinstance(data, Mapping) or data.get("schema_version") != RUNTIME_SCHEMA_VERSION:
            raise StateError(f"{context}: not a runtime record of schema_version {RUNTIME_SCHEMA_VERSION}")
        if set(data) != _RUNTIME_KEYS:
            raise StateError(f"{context}: unexpected runtime record fields")
        for key in ("batch", "run_id", "hostname", "started_at"):
            if not isinstance(data[key], str) or not data[key]:
                raise StateError(f"{context}: malformed runtime record: {key} must be a non-empty string")
        for key, minimum in (("index", 0), ("pid", 1)):
            if isinstance(data[key], bool) or not isinstance(data[key], int) or data[key] < minimum:
                raise StateError(f"{context}: malformed runtime record: {key} must be an integer >= {minimum}")
        return cls(
            batch=data["batch"],
            index=data["index"],
            run_id=data["run_id"],
            pid=data["pid"],
            hostname=data["hostname"],
            started_at=data["started_at"],
        )


def runtime_path(batches_dir: Path, batch_id: str) -> Path:
    return Path(batches_dir) / RUNTIME_DIRNAME / f"{batch_id}.json"


def list_runtime_files(batches_dir: Path) -> list[Path]:
    runtime_dir = Path(batches_dir) / RUNTIME_DIRNAME
    if not runtime_dir.is_dir():
        return []
    return sorted(p for p in runtime_dir.iterdir() if p.suffix == ".json" and not p.name.startswith(".") and p.is_file())


def load_runtime(batches_dir: Path, batch_id: str) -> RuntimeRecord | None:
    path = runtime_path(batches_dir, batch_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError(f"{path.name}: {exc}") from exc
    return RuntimeRecord.from_dict(data, context=path.name)


def save_runtime(batches_dir: Path, record: RuntimeRecord) -> Path:
    path = runtime_path(batches_dir, record.batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomically(path, json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n", prefix=f".{record.batch}-")
    return path


def clear_runtime(batches_dir: Path, batch_id: str) -> None:
    try:
        os.unlink(runtime_path(batches_dir, batch_id))
    except FileNotFoundError:
        pass


def running_entry(batch_id: str, state: BatchState) -> RunState | None:
    """The one run the committed state records as ``running`` (with the run
    id its container derives from), or ``None``.  More than one, or one
    without a run id, is a :class:`StateError`: one scheduler runs one
    container at a time, so such a state can only be inspected by hand."""
    running = state.running
    if len(running) > 1:
        raise StateError(
            f"batch {batch_id}: {len(running)} runs are recorded as running (entries"
            f" {', '.join(f'#{run.index}' for run in running)}); one scheduler runs one at a time"
        )
    if running and not running[0].run_id:
        raise StateError(f"batch {batch_id}: run #{running[0].index} is recorded as running without a run id")
    return running[0] if running else None


def bind_runtime(batch_id: str, runtime: RuntimeRecord, state: BatchState | None) -> RunState:
    """The committed entry *runtime* belongs to: its batch must be
    *batch_id* and its index must name an entry of *state* carrying exactly
    its run id.  That entry's run id — never the record — is what a
    container name is derived from.  Anything less is a :class:`StateError`
    and no container is touched."""
    where = f"{RUNTIME_DIRNAME}/{batch_id}.json"
    if runtime.batch != batch_id:
        raise StateError(f"{where} records batch {runtime.batch!r}, not {batch_id!r}")
    if state is None:
        raise StateError(
            f"{where} names run {runtime.run_id} at entry #{runtime.index}, but the batch has no"
            " readable committed state to bind it to"
        )
    if runtime.index >= len(state.runs):
        raise StateError(
            f"{where} names entry #{runtime.index}, but the committed state records only"
            f" {len(state.runs)} run(s)"
        )
    run = state.runs[runtime.index]
    if run.run_id != runtime.run_id:
        raise StateError(
            f"{where} names run {runtime.run_id} at entry #{runtime.index}, but the committed"
            f" state records {run.run_id!r} there"
        )
    return run


# ---------------------------------------------------------------------------
# Container reconciliation
# ---------------------------------------------------------------------------


class ContainerRuntime(Protocol):
    """What reconciliation needs from the container engine: whether a named
    container exists (its status, or ``None``), and a forced removal.  The
    production implementation drives the docker CLI; tests inject a fake."""

    def status(self, name: str) -> str | None: ...

    def remove(self, name: str) -> None: ...


class DockerContainerRuntime:
    """The docker CLI as a :class:`ContainerRuntime`.  Every failure to *know*
    is a :class:`ReconciliationError` — an unconfirmed container is treated
    as possibly running."""

    def __init__(self, binary: str = "docker") -> None:
        self._binary = binary

    def _run(self, args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self._binary, *args], capture_output=True, text=True, check=False, timeout=timeout
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReconciliationError(f"docker {args[0]} could not run: {exc}") from exc

    def status(self, name: str) -> str | None:
        proc = self._run(["container", "inspect", "--format", "{{.State.Status}}", name], timeout=30)
        if proc.returncode == 0:
            return proc.stdout.strip() or "unknown"
        if "no such" in (proc.stderr or "").lower():
            return None
        raise ReconciliationError(f"docker inspect {name} failed: {(proc.stderr or '').strip()}")

    def remove(self, name: str) -> None:
        proc = self._run(["rm", "--force", name], timeout=60)
        if proc.returncode != 0 and "no such" not in (proc.stderr or "").lower():
            raise ReconciliationError(f"docker rm --force {name} failed: {(proc.stderr or '').strip()}")


def reconcile_container(runtime: ContainerRuntime, name: str) -> str:
    """Force-remove *name* if it exists and confirm it is gone; returns a
    short note (``absent`` or ``removed (<status>)``).  Anything short of a
    confirmed absence is a :class:`ReconciliationError`."""
    status = runtime.status(name)
    if status is None:
        return "absent"
    runtime.remove(name)
    remaining = runtime.status(name)
    if remaining is not None:
        raise ReconciliationError(
            f"container {name} is still present (status {remaining}) after `docker rm"
            " --force`; its removal cannot be confirmed"
        )
    return f"removed ({status})"


# ---------------------------------------------------------------------------
# The single-writer lock
# ---------------------------------------------------------------------------


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
        holder = {"pid": os.getpid(), "hostname": socket.gethostname(), "started_at": _stamp(_now())}
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


# ---------------------------------------------------------------------------
# Classification of a batch: runnable, or blocked and why
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchBlock:
    """Why nothing from a batch may run: the kind (:data:`BLOCK_MISSING_STATE`,
    :data:`BLOCK_UNREADABLE_STATE`, :data:`BLOCK_ABANDONED_RUN`) and the
    operator-facing message."""

    kind: str
    message: str


def missing_state_warning(batch_id: str) -> str:
    return (
        f"no committed state ({BATCHES_DIRNAME}/{STATE_DIRNAME}/{batch_id}.json is absent):"
        " nothing from this batch runs. Restore the committed checkpoint, or acknowledge"
        f" the replay for this batch only with `silverquillm scheduler --replay-without-state"
        f" {batch_id}` — starting from entry 0 may REPLAY runs already completed elsewhere"
        " and incur model and runtime costs"
    )


def inspect_batch(
    batches_dir: Path, batch_id: str, *, hostname: str | None = None
) -> tuple[BatchState | None, BatchBlock | None]:
    """``(state, block)`` for one batch id — the one classification the
    scheduler and the read-only views share.  Reads only."""
    hostname = hostname or socket.gethostname()
    try:
        state = load_state(batches_dir, batch_id)
    except StateError as exc:
        return None, BatchBlock(
            BLOCK_UNREADABLE_STATE,
            f"committed state is unreadable ({exc}); nothing from this batch runs until it is"
            " restored or repaired by hand",
        )
    if state is None:
        return None, BatchBlock(BLOCK_MISSING_STATE, missing_state_warning(batch_id))
    try:
        run = running_entry(batch_id, state)
    except StateError as exc:
        return state, BatchBlock(
            BLOCK_ABANDONED_RUN,
            f"committed state is inconsistent ({exc}); nothing from this batch runs until it is"
            " repaired by hand",
        )
    if run is None:
        return state, None
    container = container_name(run.run_id or "")
    runtime: RuntimeRecord | None = None
    bound: RunState | None = None
    binding_error: StateError | None = None
    try:
        runtime = load_runtime(batches_dir, batch_id)
        bound = bind_runtime(batch_id, runtime, state) if runtime is not None else None
    except StateError as exc:
        binding_error = exc
    if binding_error is not None:
        message = (
            f"run #{run.index} ({run.run_id}) is recorded as running and this host's runtime"
            f" metadata does not bind to it ({binding_error}); the scheduler stops until it is"
            f" inspected by hand — confirm container {container} is gone (`docker ps`), then delete"
            f" {RUNTIME_DIRNAME}/{batch_id}.json; --acknowledge-cleanup is refused meanwhile"
        )
    elif runtime is None:
        message = (
            f"run #{run.index} ({run.run_id}) is recorded as running but this host holds no"
            " runtime metadata for it — the state was committed on another host and the"
            f" run cannot be reconciled here. Confirm container {container}"
            " is gone on the host that ran it, then start the scheduler with"
            f" --acknowledge-cleanup {batch_id}"
        )
    elif bound is not run:
        message = (
            f"run #{run.index} ({run.run_id}) is recorded as running but this host's runtime"
            f" metadata binds to entry #{bound.index} ({bound.run_id}); the scheduler stops until"
            f" it is inspected by hand — confirm container {container} is gone, then delete"
            f" {RUNTIME_DIRNAME}/{batch_id}.json"
        )
    elif runtime.hostname == hostname:
        message = (
            f"run #{run.index} ({run.run_id}) was left running by scheduler pid"
            f" {runtime.pid} on this host; its container {container} is"
            " reconciled (force-removed and confirmed gone) when a scheduler starts"
        )
    else:
        message = (
            f"run #{run.index} ({run.run_id}) was left running on host {runtime.hostname!r} and"
            f" cannot be reconciled here. Confirm container {container} is gone on that host,"
            f" then start the scheduler with --acknowledge-cleanup {batch_id}"
        )
    return state, BatchBlock(BLOCK_ABANDONED_RUN, message)


# ---------------------------------------------------------------------------
# Resolution and execution
# ---------------------------------------------------------------------------


def resolve_candidate_ref(ref: str, *, repo_root: Path) -> Path:
    """A batch's ``candidate`` — an absolute path, a path relative to the
    bench repo, or a bare ``candidates/`` entry name — as a directory."""
    if not isinstance(ref, str) or not ref.strip():
        raise SchedulerError("candidate ref must be a non-empty string")
    path = Path(ref)
    tried: list[Path] = [path] if path.is_absolute() else [Path(repo_root) / ref]
    if not path.is_absolute() and "/" not in ref:
        tried.append(Path(repo_root) / "candidates" / ref)
    for option in tried:
        if option.is_dir():
            return option.resolve()
    raise SchedulerError(
        f"candidate ref {ref!r} resolves to no directory (tried {', '.join(str(t) for t in tried)})"
    )


@dataclass(frozen=True)
class ResolvedRun:
    """Everything the executor needs, resolved at run start."""

    batch_id: str
    index: int
    spec: RunSpec
    run_id: str
    run_dir: Path
    candidate_path: Path
    bundle: CandidateBundle
    benchmark: BenchmarkRef
    mode: BenchmarkMode
    results_repo: Path | None

    @property
    def container(self) -> str:
        """The deterministic name the driver gives this run's container."""
        return container_name(self.run_id)


@dataclass(frozen=True)
class RunOutcome:
    """What one executed run came to."""

    ok: bool
    summary: str = ""
    failure_class: str | None = None
    record_dir: Path | None = None


Executor = Callable[[ResolvedRun], RunOutcome]


def contract_run_executor(
    *,
    container_user: str | None = None,
    environ: Mapping[str, str] | None = None,
    eval_timeout: int = 60,
) -> Executor:
    """The production executor: the bundle run path
    (:func:`silverquillm.contract.drive_contract_run` over the Docker session
    factory).  The bundle the scheduler verified at run start is the one the
    driver runs — the identity in the state file and in the RunRecord are the
    same recomputation."""

    def execute(resolved: ResolvedRun) -> RunOutcome:
        from theozolith_worker import api

        from silverquillm.contract import drive_contract_run

        result = drive_contract_run(
            run_dir=resolved.run_dir,
            run_id=resolved.run_id,
            benchmark=resolved.benchmark,
            mode=resolved.mode,
            budget_seconds=resolved.spec.budget_seconds,
            candidate=resolved.candidate_path,
            session_factory=api.container_session_factory(api.DockerEngine()),
            results_repo=resolved.results_repo,
            eval_timeout=eval_timeout,
            environ=environ,
            container_user=container_user,
            bundle_loader=lambda path: resolved.bundle,
        )
        if result.ok:
            summary = f"phase {result.phase}; proposal {result.proposal_status}"
        else:
            failure = result.failure
            summary = f"[{failure.failure_class}] at {failure.phase}: {failure.reason}"
        return RunOutcome(
            ok=result.ok,
            summary=summary,
            failure_class=result.failure_class,
            record_dir=result.record_dir,
        )

    return execute


# ---------------------------------------------------------------------------
# The scheduler
# ---------------------------------------------------------------------------


Logger = Callable[[str], None]


@dataclass(frozen=True)
class _Reconciliation:
    """One container recovery will touch: ``container_name(run.run_id)`` for
    a committed entry a runtime record binds to.  *stale* when the entry is
    already terminal (only the runtime file is left over)."""

    batch_id: str
    state: BatchState
    run: RunState
    stale: bool


def _default_log(message: str) -> None:
    print(f"{_stamp(_now())} {message}", flush=True)


class Scheduler:
    """The single-writer loop over ``batches/``.

    *executor* runs one resolved run and returns its :class:`RunOutcome` (the
    production one is :func:`contract_run_executor`; tests inject a stub).
    *container_runtime* reconciles abandoned containers (the production one
    is :class:`DockerContainerRuntime`; tests inject a fake).  *now* /
    *sleep* / *log* / *hostname* are injectable clocks, sinks and identity;
    every line reaches *log* through :meth:`_log`, redacted.  *environ* is
    the effective environment the executor binds secret slots from
    (``os.environ`` by default): the exact values bound to a bundle's
    declared slots are redacted from everything the scheduler records or
    logs.  *replay_without_state* and *acknowledge_cleanup* are the
    operator's batch-scoped acknowledgements, applied once under the lock at
    startup.
    """

    def __init__(
        self,
        batches_dir: Path,
        *,
        executor: Executor,
        container_runtime: ContainerRuntime | None = None,
        repo_root: Path | None = None,
        runs_root: Path | None = None,
        results_repo: Path | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        log: Logger | None = None,
        hostname: str | None = None,
        environ: Mapping[str, str] | None = None,
        replay_without_state: Iterable[str] = (),
        acknowledge_cleanup: Iterable[str] = (),
    ) -> None:
        self.batches_dir = Path(batches_dir)
        self.executor = executor
        self._container_runtime = container_runtime
        self._environ: Mapping[str, str] = os.environ if environ is None else environ
        self.repo_root = Path(repo_root) if repo_root is not None else _REPO_ROOT
        self.runs_root = Path(runs_root) if runs_root is not None else self.repo_root / RUNS_DIRNAME
        self.results_repo = Path(results_repo) if results_repo is not None else None
        self.poll_seconds = poll_seconds
        self.hostname = hostname or socket.gethostname()
        self.replay_without_state = tuple(replay_without_state)
        self.acknowledge_cleanup = tuple(acknowledge_cleanup)
        self._now = now or _now
        self._sleep = sleep or time.sleep
        self._sink: Logger = log or _default_log
        self._reported: dict[Path, tuple[float, str]] = {}
        self._acknowledged = False

    @property
    def container_runtime(self) -> ContainerRuntime:
        if self._container_runtime is None:
            self._container_runtime = DockerContainerRuntime()
        return self._container_runtime

    # -- sanitizing what reaches the committed state and the log -------------

    def _roots(self) -> list[tuple[str, str]]:
        roots: list[tuple[str, str]] = [
            ("<runs>", str(self.runs_root)),
            ("<repo>", str(self.repo_root)),
            ("<repo>", str(_REPO_ROOT)),
        ]
        if self.results_repo is not None:
            roots.append(("<results-repo>", str(self.results_repo)))
        roots.append(("<batches>", str(self.batches_dir)))
        try:
            roots.append(("<home>", str(Path.home())))
        except (OSError, RuntimeError):
            pass
        roots.append(("<tmp>", tempfile.gettempdir()))
        return [(p, r) for p, r in sorted(roots, key=lambda item: -len(item[1])) if len(Path(r).parts) >= 2]

    def _redact(self, text: str, *, bundle: CandidateBundle | None = None) -> str:
        """Every secret value and host-local root gone, line structure kept
        (what a log line may carry).  With *bundle*: the exact non-empty
        value bound to each of its declared secret slots in the effective
        environment — whatever its shape — and one of those slots assigned
        any non-empty value, whatever its length or characters; always: every
        generic credential shape; then the known roots replaced by
        placeholders.  Without a bundle (a spec that never
        resolved) the generic shapes and roots still apply."""
        slots = tuple(bundle.secret_slots) if bundle is not None else ()
        bound = sorted(((slot, self._environ.get(slot, "")) for slot in slots), key=lambda item: -len(item[1]))
        for slot, value in bound:
            if value:
                text = text.replace(value, f"[redacted: value bound to secret slot {slot}]")
        text = redact_credentials(text, secret_slots=slots)
        for placeholder, root in self._roots():
            text = text.replace(root, placeholder)
        return text

    def _sanitize(self, text: str, *, bundle: CandidateBundle | None = None) -> str:
        """:meth:`_redact`, then one line and capped — what a committed state
        file may carry."""
        text = " ".join(self._redact(text, bundle=bundle).split())
        if len(text) > _ERROR_MAX_CHARS:
            text = text[: _ERROR_MAX_CHARS - 1] + "…"
        return text

    def _log(self, message: str, *, bundle: CandidateBundle | None = None) -> None:
        """The one way a line reaches the log sink: :meth:`_redact` first,
        always — every generic credential shape and known host root — and,
        given the *bundle* a run resolved to, its declared slots' exact bound
        values and assignments too.  Line structure is kept."""
        self._sink(self._redact(message, bundle=bundle))

    # -- observation ---------------------------------------------------------

    def _report_once(self, path: Path, message: str) -> None:
        """Log a per-file problem once per file version (mtime + message)."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        if self._reported.get(path) != (mtime, message):
            self._reported[path] = (mtime, message)
            self._log(message)

    def next_work(self) -> tuple[Batch, BatchState, int] | None:
        """The first due, unblocked batch with an unconsumed entry, re-read
        from disk."""
        now = self._now()
        for path in list_batch_files(self.batches_dir):
            try:
                batch = load_batch(path)
            except BatchError as exc:
                self._report_once(path, f"SKIPPED malformed {path.name}: {exc}")
                continue
            state, block = inspect_batch(self.batches_dir, batch.id, hostname=self.hostname)
            if block is not None:
                key = path if block.kind == BLOCK_MISSING_STATE else state_path(self.batches_dir, batch.id)
                self._report_once(key, f"BLOCKED {batch.id} [{block.kind}]: {block.message}")
                continue
            assert state is not None
            if not batch.due(now):
                continue
            if state.consumed < len(batch.runs):
                return batch, state, state.consumed
        return None

    # -- startup: acknowledgements, then reconciliation -----------------------

    def apply_acknowledgements(self) -> None:
        """Apply ``--replay-without-state`` / ``--acknowledge-cleanup`` once,
        under the lock.  Each names one batch and must apply to it exactly,
        or the scheduler refuses to start."""
        if self._acknowledged:
            return
        for batch_id in self.replay_without_state:
            batch_file = self.batches_dir / f"{batch_id}{BATCH_SUFFIX}"
            if batch_file not in list_batch_files(self.batches_dir):
                raise AcknowledgementError(
                    f"--replay-without-state {batch_id}: no batch file {batch_file.name} in"
                    f" {self.batches_dir}; the acknowledgement names a batch that does not exist"
                )
            if state_path(self.batches_dir, batch_id).exists():
                raise AcknowledgementError(
                    f"--replay-without-state {batch_id}: {STATE_DIRNAME}/{batch_id}.json already"
                    " exists — there is no missing state to acknowledge; delete the state"
                    " file by hand only if you really mean to replay the batch from entry 0"
                )
            save_state(self.batches_dir, BatchState(batch=batch_id, batch_file=batch_file.name), now=self._now())
            self._log(
                f"REPLAY ACKNOWLEDGED {batch_id}: created empty {STATE_DIRNAME}/{batch_id}.json;"
                " the batch starts from entry 0 (commit the state file with the batch)"
            )
        for batch_id in self.acknowledge_cleanup:
            state, run = self._acknowledgeable_run(batch_id)
            self._finish_abandoned(run, note="cleanup acknowledged by the operator (--acknowledge-cleanup)")
            save_state(self.batches_dir, state, now=self._now())
            clear_runtime(self.batches_dir, batch_id)
            self._log(
                f"CLEANUP ACKNOWLEDGED {batch_id}: run #{run.index} ({run.run_id}) marked failed on"
                " the operator's word"
            )
        self._acknowledged = True

    def _acknowledgeable_run(self, batch_id: str) -> tuple[BatchState, RunState]:
        """The run ``--acknowledge-cleanup`` may mark failed — only when local
        reconciliation is impossible: no runtime metadata on this checkout,
        or a valid record that belongs to another host.  Valid same-host
        metadata means the run is reconciled here instead; unreadable,
        malformed or unbound metadata fails closed with the file kept."""
        flag = f"--acknowledge-cleanup {batch_id}"
        try:
            state = load_state(self.batches_dir, batch_id)
        except StateError as exc:
            raise AcknowledgementError(f"{flag}: committed state is unreadable ({exc}); nothing can be acknowledged") from None
        try:
            run = running_entry(batch_id, state) if state is not None else None
        except StateError as exc:
            raise AcknowledgementError(f"{flag}: {exc}; repair the committed state by hand") from None
        if state is None or run is None:
            raise AcknowledgementError(
                f"{flag}: batch {batch_id} has no run recorded as running; there is nothing to acknowledge"
            )
        container = container_name(run.run_id or "")
        try:
            runtime = load_runtime(self.batches_dir, batch_id)
            bound = bind_runtime(batch_id, runtime, state) if runtime is not None else None
        except StateError as exc:
            raise AcknowledgementError(
                f"{flag}: {RUNTIME_DIRNAME}/{batch_id}.json is unreadable or does not bind to the"
                f" recorded run ({exc}); the acknowledgement cannot stand in for an inspection —"
                f" confirm container {container} is gone (`docker ps`), delete the runtime file by"
                " hand, and start again; the file is kept"
            ) from None
        if runtime is not None and bound is not run:
            raise AcknowledgementError(
                f"{flag}: {RUNTIME_DIRNAME}/{batch_id}.json binds to entry #{bound.index}"
                f" ({bound.run_id}), not to the running entry #{run.index} ({run.run_id}); inspect by"
                f" hand — confirm container {container} is gone, then delete the runtime file"
            )
        if runtime is not None and runtime.hostname == self.hostname:
            raise AcknowledgementError(
                f"{flag}: this host holds runtime metadata for run {run.run_id} (scheduler pid"
                f" {runtime.pid}), so the run is reconciled here — start without the flag and"
                f" container {container} is force-removed and confirmed gone"
            )
        return state, run

    def _finish_abandoned(self, run: RunState, *, note: str) -> None:
        run.state = RUN_FAILED
        run.ok = False
        run.failure_class = FAILURE_ABANDONED
        run.finished_at = _stamp(self._now())
        run.summary = run.summary or "abandoned"
        run.error = self._sanitize(
            f"the scheduler exited while this run was running; {note}; marked failed at scheduler startup"
        )

    def recover(self) -> list[str]:
        """Reconcile every run left ``running`` by a previous scheduler before
        any new work: on this host, force-remove its container and confirm it
        gone, then mark the run failed; anything that cannot be confirmed
        stops the scheduler (:class:`ReconciliationError`).  Every runtime
        record is bound to its committed entry first — across all batches,
        before the first container operation — so a record that does not
        bind stops the scheduler with nothing touched.  Called under the lock
        at startup; returns the run ids touched."""
        touched: list[str] = []
        for item in self._plan_recovery():
            container = container_name(item.run.run_id or "")
            note = reconcile_container(self.container_runtime, container)
            if item.stale:
                self._log(f"RECOVERED {item.batch_id}: stale runtime metadata for {item.run.run_id} — container {note}")
            else:
                self._finish_abandoned(item.run, note=f"container {note}")
                save_state(self.batches_dir, item.state, now=self._now())
                touched.append(item.run.run_id or f"{item.batch_id}#{item.run.index}")
                self._log(f"RECOVERED {item.batch_id} #{item.run.index}: {item.run.run_id} — container {container} {note}")
            clear_runtime(self.batches_dir, item.batch_id)
        return touched

    def _plan_recovery(self) -> list[_Reconciliation]:
        """Bind every batch's runtime record to its committed entry and decide
        what recovery will do — reading only.  Any record that is unreadable,
        malformed, unbound or from another host, and any running entry
        without a same-host record, is a :class:`ReconciliationError` raised
        before any container is inspected or removed."""
        items: list[_Reconciliation] = []
        batch_ids = {batch_id_of(path) for path in list_batch_files(self.batches_dir)}
        batch_ids.update(path.stem for path in list_runtime_files(self.batches_dir))
        for batch_id in sorted(batch_ids):
            where = f"{RUNTIME_DIRNAME}/{batch_id}.json"
            try:
                state = load_state(self.batches_dir, batch_id)
            except StateError:
                state = None  # blocked as unreadable by next_work; a runtime file cannot bind to it
            try:
                runtime = load_runtime(self.batches_dir, batch_id)
            except StateError as exc:
                raise ReconciliationError(
                    f"{where} is unreadable ({exc}); a run of batch {batch_id} may still hold a"
                    " container on this host — inspect `docker ps`, remove the container by hand,"
                    " delete the runtime file, and start again"
                ) from None
            try:
                run = running_entry(batch_id, state) if state is not None else None
                bound = bind_runtime(batch_id, runtime, state) if runtime is not None else None
            except StateError as exc:
                raise ReconciliationError(
                    f"{exc}; a run of batch {batch_id} may still hold a container on this host —"
                    " inspect `docker ps`, remove the container by hand, delete the runtime file,"
                    " and start again"
                ) from None
            if runtime is not None and runtime.hostname != self.hostname:
                raise ReconciliationError(
                    f"{where} was written on host {runtime.hostname!r}, not this one"
                    f" ({self.hostname!r}): run {runtime.run_id} cannot be reconciled here. Confirm"
                    f" container {container_name(runtime.run_id)} is gone on that host, delete the"
                    " runtime file, and start again"
                    + (f" with --acknowledge-cleanup {batch_id}" if run is not None else "")
                )
            if run is not None:
                if runtime is None:
                    raise ReconciliationError(
                        f"batch {batch_id} run #{run.index} ({run.run_id}) is recorded as running"
                        " but this host holds no runtime metadata for it — the state was"
                        " committed on another host and the run cannot be reconciled here."
                        f" Confirm container {container_name(run.run_id or '')} is gone on the"
                        f" host that ran it, then start again with --acknowledge-cleanup {batch_id}"
                    )
                if bound is not run:
                    raise ReconciliationError(
                        f"{where} binds to entry #{bound.index} ({bound.run_id}) while entry"
                        f" #{run.index} ({run.run_id}) is recorded as running; the state and the"
                        " runtime metadata disagree — inspect `docker ps`, remove any container of"
                        " this batch by hand, delete the runtime file, and start again"
                    )
                assert state is not None
                items.append(_Reconciliation(batch_id=batch_id, state=state, run=run, stale=False))
            elif runtime is not None:
                # The previous scheduler died between the terminal transition
                # and the cleanup: the bound (terminal) entry's container is
                # reconciled anyway.
                assert state is not None and bound is not None
                items.append(_Reconciliation(batch_id=batch_id, state=state, run=bound, stale=True))
        return items

    # -- execution -----------------------------------------------------------

    def _resolve(self, batch: Batch, index: int, spec: RunSpec) -> ResolvedRun:
        candidate_path = resolve_candidate_ref(spec.candidate, repo_root=self.repo_root)
        bundle = load_candidate_bundle(candidate_path)
        benchmark = load_benchmark(spec.benchmark, repo_root=self.repo_root)
        mode = get_mode(spec.mode)
        label = candidate_label(candidate_path)
        results_dir = self.runs_root / label
        run_id = new_run_name(benchmark.id, label, results_dir)
        return ResolvedRun(
            batch_id=batch.id,
            index=index,
            spec=spec,
            run_id=run_id,
            run_dir=results_dir / run_id,
            candidate_path=candidate_path,
            bundle=bundle,
            benchmark=benchmark,
            mode=mode,
            results_repo=self.results_repo,
        )

    def run_next(self) -> bool:
        """Start and finish the next due run; ``False`` when nothing is due."""
        work = self.next_work()
        if work is None:
            return False
        batch, state, index = work
        spec = batch.runs[index]
        started = self._now()
        entry = RunState(
            index=index,
            spec=portable_spec(spec),
            state=RUN_RUNNING,
            started_at=_stamp(started),
        )
        state.runs.append(entry)
        try:
            resolved = self._resolve(batch, index, spec)
        except Exception as exc:  # noqa: BLE001 - every resolution failure is a failed run
            entry.state = RUN_FAILED
            entry.ok = False
            entry.failure_class = FAILURE_UNRESOLVABLE
            entry.error = self._sanitize(f"{type(exc).__name__}: {exc}")
            entry.summary = "run spec could not be resolved"
            entry.finished_at = _stamp(self._now())
            save_state(self.batches_dir, state, now=self._now())
            self._log(f"FAILED {batch.id} #{index}: {type(exc).__name__}: {exc}")
            return True

        entry.run_id = resolved.run_id
        entry.candidate_hash = candidate_hash(resolved.bundle.identity)
        entry.hash8 = candidate_hash8(resolved.bundle.identity)
        entry.identity = resolved.bundle.identity.to_dict()
        entry.resolved_at = _stamp(self._now())
        # Runtime metadata first, then the committed transition: a running
        # entry on this host always has the metadata a replacement needs.
        save_runtime(
            self.batches_dir,
            RuntimeRecord(
                batch=batch.id,
                index=index,
                run_id=resolved.run_id,
                pid=os.getpid(),
                hostname=self.hostname,
                started_at=entry.started_at or _stamp(started),
            ),
        )
        resolved.run_dir.mkdir(parents=True, exist_ok=True)
        save_state(self.batches_dir, state, now=self._now())
        self._log(
            f"STARTED {batch.id} #{index}: {resolved.run_id} — candidate"
            f" {resolved.bundle.worker_type} [{entry.hash8}] mode {spec.mode}"
            f" benchmark {spec.benchmark} budget {spec.budget_seconds}s",
            bundle=resolved.bundle,
        )
        try:
            outcome = self.executor(resolved)
        except Exception as exc:  # noqa: BLE001 - an executor crash is a failed run, not a dead scheduler
            outcome = RunOutcome(
                ok=False, summary=f"executor raised {type(exc).__name__}", failure_class=FAILURE_SCHEDULER
            )
            entry.error = self._sanitize(f"{type(exc).__name__}: {exc}", bundle=resolved.bundle)
            self._log(
                f"EXECUTOR ERROR {batch.id} #{index}: " + "".join(traceback.format_exception(exc)).rstrip(),
                bundle=resolved.bundle,
            )
        except BaseException as exc:  # SIGINT / SIGTERM: interrupt the run, then unwind
            self._interrupt(batch, index, state, entry, resolved, exc)
            raise
        entry.state = RUN_DONE if outcome.ok else RUN_FAILED
        entry.ok = outcome.ok
        entry.failure_class = outcome.failure_class
        entry.summary = self._sanitize(outcome.summary, bundle=resolved.bundle)
        entry.finished_at = _stamp(self._now())
        save_state(self.batches_dir, state, now=self._now())
        clear_runtime(self.batches_dir, batch.id)
        self._log(
            f"{'DONE' if outcome.ok else 'FAILED'} {batch.id} #{index}: {resolved.run_id} — {entry.summary}",
            bundle=resolved.bundle,
        )
        return True

    def _interrupt(
        self, batch: Batch, index: int, state: BatchState, entry: RunState, resolved: ResolvedRun, exc: BaseException
    ) -> None:
        """The run in flight was interrupted (Ctrl-C, SIGTERM): remove its
        container and record the run failed.  If the container cannot be
        confirmed gone, the entry stays ``running`` with its runtime metadata
        so the next scheduler reconciles it at startup."""
        why = "SIGTERM" if isinstance(exc, SchedulerStopped) else type(exc).__name__
        try:
            note = reconcile_container(self.container_runtime, resolved.container)
        except ReconciliationError as rexc:
            self._log(
                f"INTERRUPTED {batch.id} #{index}: {resolved.run_id} ({why}) — container"
                f" {resolved.container} could NOT be removed: {rexc}; the run stays recorded as"
                " running and is reconciled when a scheduler next starts",
                bundle=resolved.bundle,
            )
            return
        entry.state = RUN_FAILED
        entry.ok = False
        entry.failure_class = FAILURE_INTERRUPTED
        entry.summary = f"interrupted ({why})"
        entry.error = self._sanitize(
            f"the scheduler was interrupted ({why}) while this run was running; container {note}",
            bundle=resolved.bundle,
        )
        entry.finished_at = _stamp(self._now())
        save_state(self.batches_dir, state, now=self._now())
        clear_runtime(self.batches_dir, batch.id)
        self._log(
            f"INTERRUPTED {batch.id} #{index}: {resolved.run_id} ({why}) — container {resolved.container} {note}",
            bundle=resolved.bundle,
        )

    # -- the loops -----------------------------------------------------------

    def _start(self) -> None:
        """Under the lock: acknowledgements, then reconciliation."""
        self.apply_acknowledgements()
        self.recover()

    def run_until_idle(self) -> int:
        """Hold the lock and run until no batch has due work; return the count."""
        with SchedulerLock(self.batches_dir), _sigterm_raises():
            self._start()
            count = 0
            while self.run_next():
                count += 1
            return count

    def serve(self) -> None:
        """Hold the lock and run forever, polling when idle."""
        with SchedulerLock(self.batches_dir), _sigterm_raises():
            self._start()
            self._log(f"scheduler serving {self.batches_dir} (poll {self.poll_seconds:g}s)")
            while True:
                if not self.run_next():
                    self._sleep(self.poll_seconds)


class _sigterm_raises:
    """While active (main thread only), SIGTERM raises :class:`SchedulerStopped`
    in the main thread instead of killing the process outright, so the run
    in flight is interrupted like a Ctrl-C and the lock, state and runtime
    metadata are left consistent.  SIGKILL cannot be caught: it leaves the
    entry ``running`` with its runtime metadata for the next startup."""

    def __init__(self) -> None:
        self._previous: Any = None
        self._installed = False

    def __enter__(self) -> Self:
        if threading.current_thread() is threading.main_thread():

            def _raise(signum: int, frame: object) -> None:
                raise SchedulerStopped(f"signal {signum}")

            self._previous = signal.signal(signal.SIGTERM, _raise)
            self._installed = True
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._installed:
            signal.signal(signal.SIGTERM, self._previous)
            self._installed = False
