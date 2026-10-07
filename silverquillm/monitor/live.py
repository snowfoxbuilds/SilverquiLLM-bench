"""Live Benchmark Runs on this host and the stage each is in (RUN-MONITORING.md, Run stages)."""

from __future__ import annotations

import enum
import os
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from silverquillm.karn.records import InvalidRunRecordError, KarnIdentity
from silverquillm.karn.subscription_usage import provider_for

from ._read import instant, mapping, read_json
from .candidates import CandidateDisplay, candidate_display
from .containers import RunContainer
from .locks import lock_held

RUN_ID_LIMIT = 64
RECOVERY_DIRECTORY = re.compile(r"recovery-[0-9]+")
CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")


class Stage(enum.Enum):
    STARTING = "starting"
    """The runner holds the run and is staging it; its container has not started."""
    RUNNING = "running"
    GRADING = "grading"
    RECORDING = "recording"
    """The runner or a recovery holds the run with a record retained: publishing or settling."""
    NEEDS_RECOVER = "needs_recover"
    UNKNOWN = "unknown"
    """The lock table is unavailable, so whether a runner still owns the run is unknown."""


@dataclass(frozen=True)
class LiveRun:
    run_id: str
    run_dir: Path
    stage: Stage
    benchmark: str | None
    construct: str | None
    candidate: CandidateDisplay
    candidate_hash: str | None
    login_profile: str | None
    provider: str | None
    budget_seconds: int | None
    host_started_at: datetime | None
    container: RunContainer | None
    native_telemetry: bool
    telemetry_adapter: str | None
    reasons: tuple[str, ...] = ()
    """Why a Needs recover or Unknown run needs recovery (RUN-MONITORING.md, Run stages)."""

    @property
    def started_at(self) -> datetime | None:
        """The container's start, which the budget runs against; else the host's."""
        if self.container is not None and self.container.started_at is not None:
            return self.container.started_at
        return self.host_started_at

    def elapsed_seconds(self, now: datetime) -> float | None:
        """Container time: up to now while running, else up to the container's stop."""
        start = self.container.started_at if self.container else None
        if start is None:
            return None
        end = now if self.container.running else (self.container.finished_at or now)
        return max(0.0, (end - start).total_seconds())


@dataclass(frozen=True)
class RetainedRecord:
    """The parts of a retained record a stage needs; the scores are never kept."""

    run_id: str
    candidate_hash: str
    stopped: bool
    recovery_of: str | None


UNREADABLE = "unreadable_record"


@dataclass
class RecordCache:
    """Retained records are never rewritten, so each is parsed once per file identity."""

    _entries: dict[Path, tuple[tuple[int, int, int], RetainedRecord | None]] = field(
        default_factory=dict
    )

    def read(self, path: Path) -> RetainedRecord | str | None:
        """The record at ``path``, None when absent, or ``UNREADABLE``."""
        try:
            info = os.stat(path, follow_symlinks=False)
        except OSError:
            self._entries.pop(path, None)
            return None
        key = (info.st_ino, info.st_mtime_ns, info.st_size)
        cached = self._entries.get(path)
        if cached is None or cached[0] != key:
            cached = (key, _retained(read_json(path)))
            self._entries[path] = cached
        return cached[1] if cached[1] is not None else UNREADABLE


def _retained(document) -> RetainedRecord | None:
    manifest = mapping(mapping(document).get("manifest"))
    metadata = mapping(manifest.get("run_metadata"))
    stopped = mapping(metadata.get("execution")).get("workspace_stopped")
    run_id, candidate_hash = manifest.get("run_id"), manifest.get("candidate_hash")
    recovery_of = metadata.get("recovery_of")
    if (
        not isinstance(run_id, str)
        or not isinstance(candidate_hash, str)
        or not CANDIDATE_HASH.fullmatch(candidate_hash)
        or not isinstance(stopped, bool)
        or not (recovery_of is None or isinstance(recovery_of, str))
    ):
        return None
    return RetainedRecord(run_id, candidate_hash, stopped, recovery_of)


@dataclass(frozen=True)
class _Records:
    original: RetainedRecord | None
    linked: RetainedRecord | None
    errors: tuple[str, ...]

    @property
    def retained(self) -> list[RetainedRecord]:
        return [record for record in (self.original, self.linked) if record is not None]


def _records(run_dir: Path, cache: RecordCache) -> _Records:
    """The run's original record and linked recovery, found as recovery finds them.

    Linked recoveries are found by their host-named directories, never through a path read
    from a file (``recovery._retained_recoveries``).
    """
    errors = []
    original = cache.read(run_dir / "run-record.json")
    if original == UNREADABLE or (original is not None and original.run_id != run_dir.name):
        errors.append(UNREADABLE)
        original = None
    try:
        entries = [
            entry for entry in os.scandir(run_dir) if RECOVERY_DIRECTORY.fullmatch(entry.name)
        ]
    except OSError:
        entries = []
    linked = []
    for entry in sorted(entries, key=lambda entry: entry.name):
        if not entry.is_dir(follow_symlinks=False):
            continue
        record = cache.read(Path(entry.path) / "run-record.json")
        if record == UNREADABLE:
            errors.append(UNREADABLE)
        elif record is not None and record.recovery_of == run_dir.name and record.stopped:
            linked.append(record)
    if len(linked) > 1:
        errors.append("ambiguous_linked_recovery")
    return _Records(original, linked[0] if len(linked) == 1 else None, tuple(dict.fromkeys(errors)))


def _published(results_repo: Path | None, record: RetainedRecord) -> bool:
    if results_repo is None:
        return True  # Without a Results Repo publication is unknown, so it is never flagged.
    return (Path(results_repo) / "results" / record.candidate_hash / record.run_id).is_dir()


def _published_without_local_record(results_repo: Path | None, run_id: str) -> bool:
    if results_repo is None:
        return False
    try:
        return any((Path(results_repo) / "results").glob("*/" + run_id))
    except (OSError, ValueError):
        return False


def _recovery_reasons(
    run_dir: Path, records: _Records, results_repo: Path | None, pending_logins: Collection[str]
) -> tuple[str, ...]:
    """Why a run still needs ``silverquillm recover``; empty once it is Finished."""
    reasons = list(records.errors)
    original = records.original
    final = records.linked or (original if original is not None and original.stopped else None)
    if final is None and not records.errors:
        if original is not None:
            reasons.append("unconfirmed_stop")
        elif not _published_without_local_record(results_repo, run_dir.name):
            reasons.append("no_record")
    if any(not _published(results_repo, record) for record in records.retained):
        reasons.append("unpublished")
    if run_dir.name in pending_logins:
        reasons.append("login_settlement_pending")
    return tuple(reasons)


def _stage(
    run_dir: Path,
    container: RunContainer | None,
    owned: bool | None,
    records: _Records,
    reasons: tuple[str, ...],
) -> Stage | None:
    """The run's stage by the first matching rule, or None once it is Finished."""
    if not owned and not reasons:
        # Finished whether or not the lock table is readable: nothing is left to own.
        return None
    if owned is None:
        return Stage.UNKNOWN
    if not owned:
        # A runner killed outright leaves its detached container running; nothing harvests it.
        return Stage.NEEDS_RECOVER
    if records.retained or records.errors:
        return Stage.RECORDING
    if container is not None and container.running:
        return Stage.RUNNING
    if container is not None or (run_dir / "host" / "host-result.json").exists():
        return Stage.GRADING
    return Stage.STARTING


def _candidate(run_dir: Path, run_input: dict) -> tuple[CandidateDisplay, str | None]:
    construct = run_input.get("construct")
    definition = None
    if isinstance(construct, str) and construct and "/" not in construct and construct[0] != ".":
        definition = read_json(run_dir / "candidate" / "constructs" / construct / "definition.json")
    try:
        candidate_hash = KarnIdentity.from_dict(run_input.get("candidate_identity")).hash
    except InvalidRunRecordError:
        candidate_hash = None
    revision = mapping(run_input.get("provenance")).get("recipe_revision")
    return candidate_display(definition, candidate_hash, revision), candidate_hash


def _live_run(
    run_dir: Path,
    container: RunContainer | None,
    held,
    *,
    results_repo: Path | None,
    pending_logins: Collection[str],
    cache: RecordCache,
) -> LiveRun | None:
    owned = lock_held(run_dir / ".runner.lock", held)
    records = _records(run_dir, cache)
    run_input = read_json(run_dir / "run-input.json")
    if not isinstance(run_input, dict):
        if container is None and not owned and not records.retained and not records.errors:
            return None  # Never launched, or not a run at all: recovery has nothing to settle.
        run_input = {}
    reasons = _recovery_reasons(run_dir, records, results_repo, pending_logins)
    stage = _stage(run_dir, container, owned, records, reasons)
    if stage is None:
        return None
    candidate, candidate_hash = _candidate(run_dir, run_input)
    telemetry = mapping(run_input.get("native_telemetry"))
    adapter = telemetry.get("adapter") if isinstance(telemetry.get("adapter"), str) else None
    login = run_input.get("login") if isinstance(run_input.get("login"), str) else None
    budget = run_input.get("budget_seconds")
    return LiveRun(
        run_id=run_dir.name,
        run_dir=run_dir,
        stage=stage,
        benchmark=run_input.get("benchmark")
        if isinstance(run_input.get("benchmark"), str)
        else None,
        construct=run_input.get("construct")
        if isinstance(run_input.get("construct"), str)
        else None,
        candidate=candidate,
        candidate_hash=candidate_hash,
        login_profile=login,
        provider=provider_for(login, adapter),
        budget_seconds=budget if type(budget) is int else None,
        host_started_at=instant(run_input.get("started_at")),
        container=container,
        native_telemetry=telemetry.get("enabled") is True,
        telemetry_adapter=adapter,
        reasons=reasons if stage in (Stage.NEEDS_RECOVER, Stage.UNKNOWN) else (),
    )


def _run_dirs(runs_dir: Path | None) -> list[Path]:
    if runs_dir is None:
        return []
    try:
        entries = list(os.scandir(runs_dir))
    except OSError:
        return []
    return [
        Path(entry.path)
        for entry in entries
        if len(entry.name) <= RUN_ID_LIMIT
        and not entry.name.startswith(".")
        and entry.is_dir(follow_symlinks=False)
    ]


def live_runs(
    runs_dir: Path | None,
    containers: list[RunContainer],
    held,
    *,
    results_repo: Path | None = None,
    pending_logins: Collection[str] = frozenset(),
    cache: RecordCache | None = None,
) -> list[LiveRun]:
    """Every run on this host that is not Finished, from its run directory and run containers.

    A container's own bind mount names its run directory, so a direct run started with
    another run directory is found too.
    """
    cache = cache if cache is not None else RecordCache()
    by_dir: dict[Path, RunContainer | None] = {path: None for path in _run_dirs(runs_dir)}
    for container in containers:
        run_dir = container.run_dir
        if run_dir is None and runs_dir is not None:
            run_dir = Path(runs_dir) / container.run_id
        if run_dir is not None and run_dir.name == container.run_id:
            by_dir[run_dir] = container
    found = []
    for run_dir, container in by_dir.items():
        run = _live_run(
            run_dir,
            container,
            held,
            results_repo=results_repo,
            pending_logins=pending_logins,
            cache=cache,
        )
        if run is not None:
            found.append(run)
    # Runs needing recovery lead the running pane; the rest run oldest first.
    return sorted(
        found,
        key=lambda run: (
            run.stage is not Stage.NEEDS_RECOVER,
            run.started_at.timestamp() if run.started_at else float("inf"),
            run.run_id,
        ),
    )
