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

from ._read import count, instant, mapping, read_json
from .candidates import CandidateDisplay, candidate_display
from .containers import RunContainer
from .history import RunSummary, validated_summary
from .locks import lock_held

RUN_ID_LIMIT = 64
RECOVERY_DIRECTORY = re.compile(r"recovery-[0-9]+")
CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


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
    record: RunSummary | None = None
    """The validated record describing this execution, None until one exists: a linked
    recovery before the original, a locally retained copy before a published one."""

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


UNREADABLE = "unreadable_record"
MISMATCHED = "mismatched_record"
UNREADABLE_PUBLISHED = "unreadable_published_record"
AMBIGUOUS_PUBLISHED = "ambiguous_published_record"


def _file_state(path: Path) -> tuple[int, int, int] | None:
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    return (info.st_ino, info.st_mtime_ns, info.st_size)


@dataclass
class RecordCache:
    """Validated Run Records, each parsed once per file identity.

    Records are never rewritten, so a record whose files keep their identity keeps its
    verdict; a record that fails the record's own validation reads as ``UNREADABLE``.
    """

    _retained: dict[Path, tuple[tuple, RunSummary | None]] = field(default_factory=dict)
    _published: dict[Path, tuple[tuple, RunSummary | None]] = field(default_factory=dict)
    _applicable: dict[Path, RunSummary] = field(default_factory=dict)

    def begin(self) -> None:
        """Start a pass; ``applicable_records`` then lists only what this pass selected."""
        self._applicable = {}

    def read(self, path: Path) -> RunSummary | str | None:
        """The retained record at ``path``, None when absent, or ``UNREADABLE``."""
        key = _file_state(path)
        if key is None:
            self._retained.pop(path, None)
            return None
        cached = self._retained.get(path)
        if cached is None or cached[0] != key:
            document = mapping(read_json(path))
            summary = validated_summary(document.get("manifest"), document.get("scores"), path)
            cached = (key, summary)
            self._retained[path] = cached
        return cached[1] if cached[1] is not None else UNREADABLE

    def published(self, directory: Path) -> RunSummary | str | None:
        """The published record in ``directory``, None when absent, or ``UNREADABLE``.

        As ``read_record`` requires, its identity must match the directory it is stored in.
        """
        if os.path.islink(directory) or not os.path.isdir(directory):
            self._published.pop(directory, None)
            return None
        manifest, scores = directory / "manifest.json", directory / "scores.json"
        key = (_file_state(manifest), _file_state(scores))
        cached = self._published.get(directory)
        if cached is None or cached[0] != key:
            summary = validated_summary(read_json(manifest), read_json(scores), directory)
            if summary is not None and (
                summary.run_id != directory.name or summary.candidate_hash != directory.parent.name
            ):
                summary = None
            cached = (key, summary)
            self._published[directory] = cached
        return cached[1] if cached[1] is not None else UNREADABLE

    def select(self, run_dir: Path, record: RunSummary | None) -> None:
        if record is not None:
            self._applicable[run_dir] = record

    def applicable_records(self) -> list[RunSummary]:
        """The one record that applies to each run directory read in this pass, Finished or
        not: the same validated, linkage-checked record the run's own view uses."""
        return list(self._applicable.values())

    def applicable_by_run(self) -> dict[str, RunSummary]:
        """``applicable_records`` keyed by the run directory's name, the execution's run id."""
        return {run_dir.name: record for run_dir, record in self._applicable.items()}


@dataclass(frozen=True)
class _Records:
    original: RunSummary | None
    linked: RunSummary | None
    errors: tuple[str, ...]

    @property
    def retained(self) -> list[RunSummary]:
        return [record for record in (self.original, self.linked) if record is not None]


def _records(run_dir: Path, cache: RecordCache) -> _Records:
    """The run's original record and linked recovery, found as recovery finds them.

    Linked recoveries are found by their host-named directories, never through a path read
    from a file (``recovery._retained_recoveries``).
    """
    errors = []
    original = cache.read(run_dir / "run-record.json")
    if original == UNREADABLE:
        errors.append(UNREADABLE)
        original = None
    elif original is not None and original.run_id != run_dir.name:
        errors.append(MISMATCHED)
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
        elif record is not None and record.recovery_of == run_dir.name and record.workspace_stopped:
            linked.append(record)
    if len(linked) > 1:
        errors.append("ambiguous_linked_recovery")
    return _Records(original, linked[0] if len(linked) == 1 else None, tuple(dict.fromkeys(errors)))


def _destination(results_repo: Path, record: RunSummary) -> Path:
    return Path(results_repo) / "results" / record.candidate_hash / record.run_id


def _published_link(
    run_dir: Path, results_repo: Path | None, cache: RecordCache
) -> RunSummary | None:
    """The published linked recovery ``recovery-record.json`` names, when it is valid.

    The link names a record only by id, as recovery reads it; anything else is ignored.
    """
    if results_repo is None:
        return None
    link = mapping(read_json(run_dir / "recovery-record.json", limit=64 * 1024))
    run_id, candidate_hash = link.get("run_id"), link.get("candidate_hash")
    if not (
        isinstance(run_id, str)
        and RUN_ID.fullmatch(run_id)
        and isinstance(candidate_hash, str)
        and CANDIDATE_HASH.fullmatch(candidate_hash)
    ):
        return None
    record = cache.published(Path(results_repo) / "results" / candidate_hash / run_id)
    if (
        isinstance(record, RunSummary)
        and record.recovery_of == run_dir.name
        and record.workspace_stopped
    ):
        return record
    return None


def _published_elsewhere(
    results_repo: Path | None, run_id: str, cache: RecordCache
) -> tuple[RunSummary | None, tuple[str, ...]]:
    """The run's only published record when this host retains none, and why it is not final."""
    if results_repo is None:
        return None, ("no_record",)
    try:
        matches = [
            path for path in (Path(results_repo) / "results").glob("*/" + run_id) if path.is_dir()
        ]
    except (OSError, ValueError):
        matches = []
    if not matches:
        return None, ("no_record",)
    if len(matches) > 1:
        return None, (AMBIGUOUS_PUBLISHED,)
    record = cache.published(matches[0])
    if not isinstance(record, RunSummary):
        return None, (UNREADABLE_PUBLISHED,)
    return record, (() if record.workspace_stopped else ("unconfirmed_stop",))


@dataclass(frozen=True)
class _Verdict:
    reasons: tuple[str, ...]
    record: RunSummary | None
    """The record whose measurements now describe the run's execution, when one exists."""


def _verdict(
    run_dir: Path,
    records: _Records,
    results_repo: Path | None,
    pending_logins: Collection[str],
    cache: RecordCache,
) -> _Verdict:
    """Why a run still needs ``silverquillm recover``, empty once it is Finished, and the
    record that applies to it; finality follows ``recovery._finalized_record``."""
    reasons = list(records.errors)
    original = records.original
    link = _published_link(run_dir, results_repo, cache)
    record = link or records.linked or original
    if link is None:
        final = records.linked or (original if original and original.workspace_stopped else None)
        if final is None and not records.errors:
            if original is not None:
                reasons.append("unconfirmed_stop")
            else:
                record, missing = _published_elsewhere(results_repo, run_dir.name, cache)
                reasons.extend(missing)
        if results_repo is not None:
            for retained in records.retained:
                published = cache.published(_destination(results_repo, retained))
                if published is None:
                    reasons.append("unpublished")
                elif published == UNREADABLE:
                    reasons.append(UNREADABLE_PUBLISHED)
    if run_dir.name in pending_logins:
        reasons.append("login_settlement_pending")
    return _Verdict(tuple(dict.fromkeys(reasons)), record)


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


def run_candidate_hash(run_dir: Path | None) -> str | None:
    """The Candidate Hash a local run directory's ``run-input.json`` names, else None."""
    if run_dir is None:
        return None
    try:
        identity = mapping(read_json(run_dir / "run-input.json")).get("candidate_identity")
        return KarnIdentity.from_dict(identity).hash
    except InvalidRunRecordError:
        return None


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
    verdict = _verdict(run_dir, records, results_repo, pending_logins, cache)
    cache.select(run_dir, verdict.record)
    reasons = verdict.reasons
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
        budget_seconds=count(budget),
        host_started_at=instant(run_input.get("started_at")),
        container=container,
        native_telemetry=telemetry.get("enabled") is True,
        telemetry_adapter=adapter,
        reasons=reasons if stage in (Stage.NEEDS_RECOVER, Stage.UNKNOWN) else (),
        record=verdict.record,
    )


def _canonical(run_dir: Path) -> Path:
    """``run_dir`` under its resolved parent, so a relative or linked run root and a
    container's absolute bind source name one run; the run directory itself is never followed.
    """
    try:
        parent = os.path.realpath(run_dir.parent)
    except (OSError, ValueError):
        try:
            parent = os.path.abspath(run_dir.parent)
        except (OSError, ValueError):
            return run_dir
    return Path(parent) / run_dir.name


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
    cache.begin()
    by_dir: dict[Path, RunContainer | None] = {
        _canonical(path): None for path in _run_dirs(runs_dir)
    }
    for container in containers:
        run_dir = container.run_dir
        if run_dir is None and runs_dir is not None:
            run_dir = Path(runs_dir) / container.run_id
        if run_dir is not None and run_dir.name == container.run_id:
            by_dir[_canonical(run_dir)] = container
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
