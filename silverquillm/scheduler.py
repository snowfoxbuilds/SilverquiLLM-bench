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
  leaves a stale lock.  A run still marked ``running`` when a scheduler
  starts (the previous process died mid-run) is marked ``failed`` at startup.

State file, ``batches/state/<id>.json``: schema-versioned, one entry per
*started* run (index, the spec as consumed, ``running`` → ``done`` /
``failed``, run id and run dir, the resolved identity and candidate hash,
timestamps, outcome summary, error), written atomically after every
transition.  The number of entries is the batch's cursor.

Public API
----------
:class:`Scheduler` (``run_next`` / ``run_until_idle`` / ``serve``),
:class:`SchedulerLock` + :func:`lock_status`, :func:`load_batch`,
:func:`list_batch_files`, :func:`load_state` / :func:`save_state`,
:func:`resolve_candidate_ref`, :func:`contract_run_executor`, the
:class:`RunSpec` / :class:`Batch` / :class:`BatchState` / :class:`RunState`
records, and :class:`RunOutcome` — the executor's result shape.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import tempfile
import time
import tomllib
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from silverquillm.candidate import CandidateBundle, load_candidate_bundle
from silverquillm.contract import RUNS_DIRNAME, candidate_label, new_run_name
from silverquillm.jobdir import BenchmarkRef, load_benchmark
from silverquillm.modes import BenchmarkMode, get_mode
from silverquillm.results_repo import candidate_hash, candidate_hash8

__all__ = [
    "BATCHES_DIRNAME",
    "BATCH_SUFFIX",
    "DEFAULT_POLL_SECONDS",
    "LOCK_FILENAME",
    "RUN_DONE",
    "RUN_FAILED",
    "RUN_PENDING",
    "RUN_RUNNING",
    "RUN_STATES",
    "STATE_DIRNAME",
    "STATE_SCHEMA_VERSION",
    "Batch",
    "BatchError",
    "BatchState",
    "Executor",
    "LockStatus",
    "ResolvedRun",
    "RunOutcome",
    "RunSpec",
    "RunState",
    "Scheduler",
    "SchedulerError",
    "SchedulerLock",
    "SchedulerLockedError",
    "StateError",
    "batch_id_of",
    "contract_run_executor",
    "list_batch_files",
    "load_batch",
    "load_state",
    "lock_status",
    "parse_batch",
    "resolve_candidate_ref",
    "save_state",
    "state_path",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent

BATCHES_DIRNAME = "batches"
STATE_DIRNAME = "state"
LOCK_FILENAME = ".scheduler.lock"
BATCH_SUFFIX = ".toml"
STATE_SCHEMA_VERSION = 1
DEFAULT_POLL_SECONDS = 30

RUN_PENDING = "pending"
RUN_RUNNING = "running"
RUN_DONE = "done"
RUN_FAILED = "failed"
RUN_STATES = (RUN_PENDING, RUN_RUNNING, RUN_DONE, RUN_FAILED)

_RUN_SPEC_KEYS = frozenset({"candidate", "mode", "benchmark", "budget_seconds"})
_BATCH_KEYS = frozenset({"not_before", "runs"})


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


class SchedulerError(Exception):
    """A scheduler-side failure (a run spec that cannot be resolved, a bad ref)."""


class BatchError(Exception):
    """A batch file is malformed; the scheduler skips it loudly."""


class StateError(Exception):
    """A scheduler state file is unreadable."""


class SchedulerLockedError(Exception):
    """Another scheduler holds ``batches/.scheduler.lock``."""


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
# Scheduler-owned execution state
# ---------------------------------------------------------------------------


@dataclass
class RunState:
    """One started run of a batch, as the scheduler observed it."""

    index: int
    spec: dict[str, Any]
    state: str
    started_at: str | None = None
    finished_at: str | None = None
    run_id: str | None = None
    run_dir: str | None = None
    candidate_path: str | None = None
    candidate_hash: str | None = None
    hash8: str | None = None
    identity: dict[str, Any] | None = None
    resolved_at: str | None = None
    pid: int | None = None
    ok: bool | None = None
    failure_class: str | None = None
    summary: str = ""
    error: str | None = None
    record_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "spec": dict(self.spec),
            "state": self.state,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "candidate_path": self.candidate_path,
            "candidate_hash": self.candidate_hash,
            "hash8": self.hash8,
            "identity": dict(self.identity) if self.identity is not None else None,
            "resolved_at": self.resolved_at,
            "pid": self.pid,
            "ok": self.ok,
            "failure_class": self.failure_class,
            "summary": self.summary,
            "error": self.error,
            "record_dir": self.record_dir,
        }

    @classmethod
    def from_dict(cls, data: Any, *, context: str) -> RunState:
        if not isinstance(data, Mapping):
            raise StateError(f"{context}: a run entry must be an object")
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
        if state not in RUN_STATES:
            raise StateError(f"{context}: unknown run state {state!r}")
        identity = data.get("identity")
        return cls(
            index=index,
            spec=dict(spec),
            state=state,
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            run_id=data.get("run_id"),
            run_dir=data.get("run_dir"),
            candidate_path=data.get("candidate_path"),
            candidate_hash=data.get("candidate_hash"),
            hash8=data.get("hash8"),
            identity=dict(identity) if isinstance(identity, Mapping) else None,
            resolved_at=data.get("resolved_at"),
            pid=data.get("pid"),
            ok=data.get("ok"),
            failure_class=data.get("failure_class"),
            summary=str(data.get("summary") or ""),
            error=data.get("error"),
            record_dir=data.get("record_dir"),
        )


@dataclass
class BatchState:
    """``batches/state/<id>.json``: every started run of the batch, in order."""

    batch: str
    batch_file: str
    runs: list[RunState] = field(default_factory=list)
    updated_at: str = ""

    @property
    def consumed(self) -> int:
        """The batch's cursor: how many of its entries have been started."""
        return len(self.runs)

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
            raise StateError(f"{context}: schema_version {version!r} is not {STATE_SCHEMA_VERSION}")
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


def load_state(batches_dir: Path, batch_id: str, *, batch_file: str = "") -> BatchState:
    """The batch's state, or an empty one when none was written yet."""
    path = state_path(batches_dir, batch_id)
    if not path.exists():
        return BatchState(batch=batch_id, batch_file=batch_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError(f"{path}: {exc}") from exc
    state = BatchState.from_dict(data, context=str(path))
    if state.batch != batch_id:
        raise StateError(f"{path}: records batch {state.batch!r}, not {batch_id!r}")
    return state


def save_state(batches_dir: Path, state: BatchState, *, now: datetime | None = None) -> Path:
    """Write the state file atomically (temp file + rename)."""
    path = state_path(batches_dir, state.batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = _stamp(now or _now())
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{state.batch}-", suffix=".json", dir=path.parent)
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
    return path


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


def _default_log(message: str) -> None:
    print(f"{_stamp(_now())} {message}", flush=True)


class Scheduler:
    """The single-writer loop over ``batches/``.

    *executor* runs one resolved run and returns its :class:`RunOutcome` (the
    production one is :func:`contract_run_executor`; tests inject a stub).
    *now* / *sleep* / *log* are injectable clocks and sinks.
    """

    def __init__(
        self,
        batches_dir: Path,
        *,
        executor: Executor,
        repo_root: Path | None = None,
        runs_root: Path | None = None,
        results_repo: Path | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        log: Logger | None = None,
    ) -> None:
        self.batches_dir = Path(batches_dir)
        self.executor = executor
        self.repo_root = Path(repo_root) if repo_root is not None else _REPO_ROOT
        self.runs_root = Path(runs_root) if runs_root is not None else self.repo_root / RUNS_DIRNAME
        self.results_repo = Path(results_repo) if results_repo is not None else None
        self.poll_seconds = poll_seconds
        self._now = now or _now
        self._sleep = sleep or time.sleep
        self._log = log or _default_log
        self._reported: dict[Path, tuple[float, str]] = {}

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
        """The first due batch with an unconsumed entry, re-read from disk."""
        now = self._now()
        for path in list_batch_files(self.batches_dir):
            try:
                batch = load_batch(path)
            except BatchError as exc:
                self._report_once(path, f"SKIPPED malformed {path.name}: {exc}")
                continue
            if not batch.due(now):
                continue
            try:
                state = load_state(self.batches_dir, batch.id, batch_file=str(path))
            except StateError as exc:
                self._report_once(state_path(self.batches_dir, batch.id), f"SKIPPED {batch.id}: unreadable state: {exc}")
                continue
            if state.consumed < len(batch.runs):
                return batch, state, state.consumed
        return None

    def recover(self) -> list[str]:
        """Mark every run left ``running`` by a previous scheduler as failed.
        Called under the lock at startup; returns the run ids touched."""
        touched: list[str] = []
        for path in list_batch_files(self.batches_dir):
            batch_id = batch_id_of(path)
            try:
                state = load_state(self.batches_dir, batch_id, batch_file=str(path))
            except StateError:
                continue
            changed = False
            for run in state.runs:
                if run.state == RUN_RUNNING:
                    run.state = RUN_FAILED
                    run.ok = False
                    run.finished_at = _stamp(self._now())
                    run.error = (
                        f"scheduler pid {run.pid} exited while this run was running;"
                        " marked failed at scheduler startup"
                    )
                    run.summary = run.summary or "interrupted"
                    touched.append(run.run_id or f"{batch_id}#{run.index}")
                    changed = True
            if changed:
                save_state(self.batches_dir, state, now=self._now())
                self._log(f"RECOVERED {batch_id}: marked interrupted run(s) failed")
        return touched

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
            spec=spec.to_dict(),
            state=RUN_RUNNING,
            started_at=_stamp(started),
            pid=os.getpid(),
        )
        state.runs.append(entry)
        try:
            resolved = self._resolve(batch, index, spec)
        except Exception as exc:  # noqa: BLE001 - every resolution failure is a failed run
            entry.state = RUN_FAILED
            entry.ok = False
            entry.failure_class = "unresolvable"
            entry.error = f"{type(exc).__name__}: {exc}"
            entry.summary = "run spec could not be resolved"
            entry.finished_at = _stamp(self._now())
            save_state(self.batches_dir, state, now=self._now())
            self._log(f"FAILED {batch.id} #{index}: {entry.error}")
            return True

        entry.run_id = resolved.run_id
        entry.run_dir = str(resolved.run_dir)
        entry.candidate_path = str(resolved.candidate_path)
        entry.candidate_hash = candidate_hash(resolved.bundle.identity)
        entry.hash8 = candidate_hash8(resolved.bundle.identity)
        entry.identity = resolved.bundle.identity.to_dict()
        entry.resolved_at = _stamp(self._now())
        resolved.run_dir.mkdir(parents=True, exist_ok=True)
        save_state(self.batches_dir, state, now=self._now())
        self._log(
            f"STARTED {batch.id} #{index}: {resolved.run_id} — candidate"
            f" {resolved.bundle.worker_type} [{entry.hash8}] mode {spec.mode}"
            f" benchmark {spec.benchmark} budget {spec.budget_seconds}s"
        )
        try:
            outcome = self.executor(resolved)
        except Exception as exc:  # noqa: BLE001 - an executor crash is a failed run, not a dead scheduler
            outcome = RunOutcome(ok=False, summary=f"executor raised {type(exc).__name__}: {exc}", failure_class="scheduler")
            entry.error = "".join(traceback.format_exception(exc))
        entry.state = RUN_DONE if outcome.ok else RUN_FAILED
        entry.ok = outcome.ok
        entry.failure_class = outcome.failure_class
        entry.summary = outcome.summary
        entry.record_dir = str(outcome.record_dir) if outcome.record_dir else None
        entry.finished_at = _stamp(self._now())
        save_state(self.batches_dir, state, now=self._now())
        self._log(f"{'DONE' if outcome.ok else 'FAILED'} {batch.id} #{index}: {resolved.run_id} — {outcome.summary}")
        return True

    def run_until_idle(self) -> int:
        """Hold the lock and run until no batch has due work; return the count."""
        with SchedulerLock(self.batches_dir):
            self.recover()
            count = 0
            while self.run_next():
                count += 1
            return count

    def serve(self) -> None:
        """Hold the lock and run forever, polling when idle."""
        with SchedulerLock(self.batches_dir):
            self.recover()
            self._log(f"scheduler serving {self.batches_dir} (poll {self.poll_seconds:g}s)")
            while True:
                if not self.run_next():
                    self._sleep(self.poll_seconds)
