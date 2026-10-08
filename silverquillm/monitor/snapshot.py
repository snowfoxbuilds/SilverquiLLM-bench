"""One poll of everything the dashboard shows, and the follows a run details view needs.

``Monitor.snapshot()`` is called on each refresh (two seconds by default); it re-reads only
what changed. Live output is followed in the background per running run, so a view polls
``Monitor.output`` for lines newer than the last sequence number it showed.
"""

from __future__ import annotations

import subprocess
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from silverquillm.host_config import (
    LOCATIONS,
    HostConfig,
    HostConfigError,
    ResolvedLocation,
    config_path,
    load_host_config,
    resolve_location,
    resolve_locations,
)
from silverquillm.karn.definition import KarnError
from silverquillm.karn.provenance import host_label as resolve_host_label

from .containers import RUN_CONTAINER_PREFIX, RunContainer, run_containers
from .costs import ProvisionalCost
from .details import RecordDetail, WorkspaceView, record_detail, workspace_view
from .estimates import WEEK, WeeklyUsage, estimated_percent, weekly_usage
from .history import HistoryStore, RepoFreshness, RunSummary, UsageReading, repo_freshness
from .live import LiveRun, RecordCache, Stage, live_runs, run_candidate_hash
from .locks import PROC_LOCKS, held_locks
from .output import LogFollower, LogLine, live_codex_reading, profile_redactions, retained_lines
from .pools import ProfileStatus, login_profiles
from .queue import QueuedBatch, queued_batches

CODEX_READING_SECONDS = 30.0
HISTORY_SECONDS = 10.0
OBSERVED_PROFILES = 64
"""At most this many Login Profiles keep a live-observed reading after their run ends."""
FINISHED_WINDOW = timedelta(days=7)
# A deeply nested file recurses; an unknown ``~user`` path fails to expand.
CONFIG_ERRORS = (HostConfigError, RecursionError, RuntimeError, ValueError, OSError)


def _config_message(error: Exception) -> str:
    if isinstance(error, HostConfigError):
        return str(error)
    return f"host configuration unreadable: {type(error).__name__}"


@dataclass(frozen=True)
class RunView:
    run: LiveRun
    estimated_percent: float | None
    """None without comparable history (RUN-MONITORING.md, Dashboard)."""
    cost: Decimal | None
    """The record's Estimated Cost once the run has one (``cost_recorded``), else the
    provisional one shown with ``~``; None when neither is known."""
    unpriced_requests: int
    request_costs: tuple[tuple[int, Decimal], ...]
    """``(timestamp_ms, usd)`` per priced request, oldest first, for a sparkline."""
    cost_recorded: bool = False
    cost_completeness: str | None = None
    """The recorded measurement's completeness; None while the cost is provisional."""
    conflicting_requests: int = 0
    """Live observations of one request that disagree, each charged once."""

    def budget_fraction(self, now: datetime) -> float | None:
        elapsed = self.run.elapsed_seconds(now)
        if elapsed is None or not self.run.budget_seconds:
            return None
        return min(1.0, elapsed / self.run.budget_seconds)


@dataclass(frozen=True)
class ProfileView:
    status: ProfileStatus
    weekly: WeeklyUsage | None
    run_id: str | None
    """The live run holding this Login Profile, when one does."""


@dataclass(frozen=True)
class Counts:
    queued: int
    live: int
    finished_recent: int
    finished_total: int


@dataclass(frozen=True)
class MonitorSnapshot:
    taken_at: datetime
    locations: Mapping[str, ResolvedLocation]
    config_file: Path
    config_error: str | None
    docker_error: str | None
    running: list[RunView]
    queued: list[QueuedBatch]
    profiles: list[ProfileView]
    counts: Counts
    repo: RepoFreshness
    exclusion_error: str | None
    host_label: str | None = None
    """This host's label; only records naming it count toward its Login Profiles."""
    records: Mapping[str, RunSummary] = field(default_factory=dict)
    """The validated record that applies to each local execution this pass, Finished or not,
    keyed by the execution's run id: the record a run details view takes its facts from."""


@dataclass
class _Live:
    run: LiveRun
    cost: ProvisionalCost
    follower: LogFollower | None = None


def _local_host_label(environ, hostname) -> str | None:
    """This host's label as run provenance records it; None when it is invalid."""
    try:
        return resolve_host_label(environ, hostname)[0]
    except KarnError:
        return None


def _spend_rank(record: RunSummary, local: bool) -> tuple:
    """Which record of one execution counts. The record selected for a run directory on
    this host comes first, so its profile and its own view agree; among published records a
    stopped linked recovery reconciles its original."""
    recovered = record.recovery_of is not None and record.workspace_stopped is True
    return (local, recovered, record.run_date.timestamp() if record.run_date else 0.0)


def _newer(reading: UsageReading, than: UsageReading | None) -> bool:
    if than is None:
        return True
    return (reading.effective_at, reading.observed_at is not None) > (
        than.effective_at,
        than.observed_at is not None,
    )


def _canonical_login(login: str | None, profiles: list[ProfileStatus]) -> str | None:
    """Records from before pools name only the slot, which kept its name when adopted."""
    if not login or "/" in login:
        return login
    matches = [profile.ref for profile in profiles if profile.slot == login]
    return matches[0] if len(matches) == 1 else login


@dataclass
class Monitor:
    given: Mapping[str, Path | str | None] = field(default_factory=dict)
    environ: Mapping[str, str] | None = None
    docker: Callable[[], tuple[list[RunContainer], str | None]] = run_containers
    proc_locks: Path = PROC_LOCKS
    popen: Callable[..., subprocess.Popen] = subprocess.Popen
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    follow_output: bool = True
    hostname: Callable[[], str] | None = None

    def __post_init__(self):
        self._config_error: str | None = None
        try:
            self.config: HostConfig = load_host_config(environ=self.environ)
        except CONFIG_ERRORS as error:
            # A broken file is reported in every snapshot, never fatal to the monitor.
            self._config_error = _config_message(error)
            self.config = HostConfig(path=config_path(self.environ), loaded=False)
        self.locations = self._resolve()
        self.host_label = _local_host_label(self.environ, self.hostname)
        self.history_store = HistoryStore(self.locations["results_repo"].path)
        self._history: list[RunSummary] = []
        self._history_at = float("-inf")
        self._live: dict[str, _Live] = {}
        self._records = RecordCache()
        self._codex_readings: dict[str, tuple[float, UsageReading | None]] = {}
        self._observed: dict[str, UsageReading] = {}
        self._repo = RepoFreshness(None, None)
        self._stopping = False

    def _resolve(self) -> dict[str, ResolvedLocation]:
        try:
            return resolve_locations(self.given, environ=self.environ, config=self.config)
        except CONFIG_ERRORS as error:
            self._config_error = self._config_error or _config_message(error)
        locations = {}
        for key in LOCATIONS:
            try:
                locations[key] = resolve_location(
                    key, self.given.get(key), environ=self.environ, config=self.config
                )
            except CONFIG_ERRORS:
                locations[key] = ResolvedLocation(key, None, "unset")
        return locations

    def path(self, key: str) -> Path | None:
        return self.locations[key].path

    def history(self, *, refresh: bool = False) -> list[RunSummary]:
        """Every record in the Results Repo clone, newest first; re-read at most every 10 s."""
        if refresh or time.monotonic() - self._history_at >= HISTORY_SECONDS:
            self._history = self.history_store.runs()
            self._repo = repo_freshness(self.path("results_repo"))
            self._history_at = time.monotonic()
        return self._history

    def _track(self, runs: list[LiveRun]) -> None:
        current = {run.run_id: run for run in runs}
        for run_id in set(self._live) - set(current):
            entry = self._live.pop(run_id)
            if entry.follower is not None:
                # The run's record may keep only an untimed copy of what was seen live.
                self._observe(entry.run.login_profile, entry.follower.reading)
                entry.follower.stop()
        for run_id, run in current.items():
            entry = self._live.get(run_id)
            if entry is None:
                entry = self._live[run_id] = _Live(
                    run, ProvisionalCost(run.run_dir, run.telemetry_adapter)
                )
            entry.run = run
            if run.native_telemetry:
                entry.cost.update()
            if (
                self.follow_output
                and not self._stopping
                and entry.follower is None
                and run.container is not None
                and run.stage is Stage.RUNNING
            ):
                entry.follower = LogFollower(
                    RUN_CONTAINER_PREFIX + run_id,
                    profile_redactions(self.path("state_root"), run.login_profile),
                    popen=self.popen,
                )
                entry.follower.start()
                if self._stopping:  # shutdown began while it was starting
                    entry.follower.signal_stop()

    def _codex_reading(self, login: str) -> UsageReading | None:
        checked = self._codex_readings.get(login)
        if checked is None or time.monotonic() - checked[0] >= CODEX_READING_SECONDS:
            checked = (time.monotonic(), live_codex_reading(self.path("state_root"), login))
            self._codex_readings[login] = checked
        return checked[1]

    def _observe(self, login: str | None, reading: UsageReading | None) -> None:
        """Keep the newest reading seen live for ``login`` beyond the follower that saw it."""
        if login is None or reading is None or reading.effective_at is None:
            return
        if _newer(reading, self._observed.get(login)):
            self._observed[login] = reading

    def _observed_readings(self, now: datetime) -> dict[str, UsageReading]:
        # A reading speaks for one window past its reset at most (estimates.weekly_usage).
        self._observed = {
            login: reading
            for login, reading in self._observed.items()
            if now < reading.resets_at + WEEK
        }
        if len(self._observed) > OBSERVED_PROFILES:
            newest = sorted(self._observed.items(), key=lambda item: item[1].effective_at)
            self._observed = dict(newest[-OBSERVED_PROFILES:])
        return self._observed

    def _accountable(self, history: list[RunSummary]) -> list[RunSummary]:
        """This host's published records that pass the record's own validation and are
        filed under their own identity; history shows the rest but they charge nothing."""
        found = []
        for summary in history:
            if not self._mine(summary):
                continue
            record = self._records.published(summary.path)
            if isinstance(record, RunSummary):
                found.append(record)
        return found

    def _executions(
        self, profiles: list[ProfileStatus], history: list[RunSummary], local: list[RunSummary]
    ) -> tuple[dict[str, tuple[str, RunSummary]], dict[str, list[UsageReading]]]:
        """For each execution this host ran, its Login Profile and the one record whose spend
        counts, and every reading those records observed per Login Profile.

        A record is this host's when it applies to a run in this host's run directory or its
        provenance names this host's label; any other record stays in history only. Only
        validated records count, so invalid evidence neither charges spend nor anchors usage.
        """
        best: dict[str, tuple[tuple, str, RunSummary]] = {}
        readings: dict[str, list[UsageReading]] = defaultdict(list)
        mine = [(summary, False) for summary in self._accountable(history)]
        for summary, local_copy in [*mine, *((summary, True) for summary in local)]:
            login = _canonical_login(summary.login_profile, profiles)
            if login is None:
                continue
            if summary.usage_reading is not None:
                readings[login].append(summary.usage_reading)
            rank = _spend_rank(summary, local_copy)
            current = best.get(summary.execution_id)
            if current is None or rank > current[0]:
                best[summary.execution_id] = (rank, login, summary)
        return {key: (login, record) for key, (_, login, record) in best.items()}, readings

    def _mine(self, summary: RunSummary) -> bool:
        return self.host_label is not None and summary.host_label == self.host_label

    def _profiles(
        self,
        profiles: list[ProfileStatus],
        history: list[RunSummary],
        local: list[RunSummary],
        now: datetime,
    ) -> list[ProfileView]:
        executions, readings = self._executions(profiles, history, local)
        costs: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
        for login, record in executions.values():
            costs[login].extend(record.request_costs)
        holder = {}
        for run_id, entry in self._live.items():
            login = entry.run.login_profile
            if login is None:
                continue
            holder[login] = run_id
            if run_id not in executions:
                costs[login].extend(
                    (row.timestamp_ms, row.usd)
                    for row in entry.cost.requests
                    if row.usd is not None
                )
            if entry.follower is not None:
                self._observe(login, entry.follower.reading)
            if entry.run.provider == "codex" and entry.run.stage is Stage.RUNNING:
                self._observe(login, self._codex_reading(login))
        for login, reading in self._observed_readings(now).items():
            readings[_canonical_login(login, profiles)].append(reading)
        return [
            ProfileView(
                profile,
                weekly_usage(
                    profile.ref,
                    profile.provider,
                    self.config.usage_rates,
                    readings[profile.ref],
                    costs[profile.ref],
                    now,
                ),
                holder.get(profile.ref),
            )
            for profile in profiles
        ]

    def _view(self, run: LiveRun, history: list[RunSummary], now: datetime) -> RunView:
        percent = (
            estimated_percent(run, history, now)
            if run.stage not in (Stage.NEEDS_RECOVER, Stage.UNKNOWN)
            else None
        )
        cost = self._live[run.run_id].cost
        record = run.record
        if record is not None:
            return RunView(
                run,
                percent,
                record.estimated_cost,
                record.unpriced_requests,
                record.request_costs,
                cost_recorded=True,
                cost_completeness=record.cost_completeness or "missing",
            )
        return RunView(
            run,
            percent,
            cost.total if run.native_telemetry else None,
            cost.unpriced,
            tuple((row.timestamp_ms, row.usd) for row in cost.requests if row.usd is not None),
            conflicting_requests=cost.conflicts,
        )

    def snapshot(self) -> MonitorSnapshot:
        now = self.clock()
        containers, docker_error = self.docker()
        held = held_locks(self.proc_locks)
        profiles = login_profiles(self.path("state_root"), held, now=now)
        runs = live_runs(
            self.path("runs_dir"),
            containers,
            held,
            results_repo=self.path("results_repo"),
            pending_logins={profile.pending_run for profile in profiles if profile.pending_run},
            cache=self._records,
        )
        self._track(runs)
        history = self.history()
        views = [self._view(run, history, now) for run in runs]
        queued = queued_batches(self.path("batches_dir"))
        recent = now - FINISHED_WINDOW
        counts = Counts(
            queued=sum(
                len(batch.runs) for batch in queued if batch.status not in ("legacy", "error")
            ),
            live=len(runs),
            finished_recent=sum(1 for run in history if run.run_date and run.run_date >= recent),
            finished_total=len(history),
        )
        return MonitorSnapshot(
            taken_at=now,
            locations=self.locations,
            config_file=self.config.path,
            config_error=self._config_error,
            docker_error=docker_error,
            running=views,
            queued=queued,
            profiles=self._profiles(profiles, history, self._records.applicable_records(), now),
            counts=counts,
            repo=self._repo,
            exclusion_error=self.history_store.exclusion_error,
            host_label=self.host_label,
            records=self._records.applicable_by_run(),
        )

    def output(self, run_id: str, stream: str | None = None, since: int = 0) -> list[LogLine]:
        """Redacted output lines of a run after sequence number ``since``.

        A live run's lines come from its follower; a finished or stopped one's from the
        retained ``host/*.log`` files in its run directory, when this host has them.
        """
        entry = self._live.get(run_id)
        if entry is not None and entry.follower is not None:
            return entry.follower.lines_since(since, stream)
        run_dir = self.run_dir(run_id)
        if run_dir is None:
            return []
        streams = (stream,) if stream else ("stdout", "stderr")
        lines = [line for name in streams for line in retained_lines(run_dir, name)]
        # Retained streams number their lines separately; together they are renumbered.
        lines = [replace(line, seq=index) for index, line in enumerate(lines, 1)]
        return [line for line in lines if line.seq > since]

    def run_dir(self, run_id: str) -> Path | None:
        """The run's directory on this host: the live one, else under the run directory."""
        entry = self._live.get(run_id)
        if entry is not None:
            return entry.run.run_dir
        runs_dir = self.path("runs_dir")
        if runs_dir is None or "/" in run_id or run_id.startswith(".") or not run_id:
            return None
        return Path(runs_dir) / run_id

    def local_candidate_hash(self, run_id: str) -> str | None:
        """The Candidate Hash this host's run directory for ``run_id`` was launched with."""
        return run_candidate_hash(self.run_dir(run_id))

    def workspace(self, run_id: str) -> WorkspaceView:
        """The run's snapshot timeline and the agent's commits, when this host has them."""
        return workspace_view(self.run_dir(run_id))

    def record_detail(self, summary: RunSummary) -> RecordDetail | None:
        """Requests, cost breakdown and failure facts from a recorded run's Run Record."""
        return record_detail(summary.path)

    def provisional_requests(self, run_id: str):
        entry = self._live.get(run_id)
        return entry.cost.requests if entry is not None else []

    def begin_shutdown(self) -> None:
        """Stop every log follower without waiting, and start no new ones.

        Safe from any thread while a poll is in progress; ``close`` still does the waiting.
        """
        self._stopping = True
        for entry in list(self._live.values()):
            if entry.follower is not None:
                entry.follower.signal_stop()

    def close(self) -> None:
        self._stopping = True
        for entry in list(self._live.values()):
            if entry.follower is not None:
                entry.follower.stop()
        self._live.clear()
