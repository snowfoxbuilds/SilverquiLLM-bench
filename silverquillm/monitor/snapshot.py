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

from .containers import RUN_CONTAINER_PREFIX, RunContainer, run_containers
from .costs import ProvisionalCost
from .details import RecordDetail, WorkspaceView, record_detail, workspace_view
from .estimates import WeeklyUsage, estimated_percent, weekly_usage
from .history import HistoryStore, RepoFreshness, RunSummary, UsageReading, repo_freshness
from .live import LiveRun, RecordCache, Stage, live_runs
from .locks import PROC_LOCKS, held_locks
from .output import LogFollower, LogLine, live_codex_reading, profile_redactions, retained_lines
from .pools import ProfileStatus, login_profiles
from .queue import QueuedBatch, queued_batches

CODEX_READING_SECONDS = 30.0
HISTORY_SECONDS = 10.0
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
    """Provisional Estimated Cost, shown with ``~``; None with native telemetry off."""
    unpriced_requests: int
    request_costs: tuple[tuple[int, Decimal], ...]
    """``(timestamp_ms, usd)`` per priced request, oldest first, for a sparkline."""

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


@dataclass
class _Live:
    run: LiveRun
    cost: ProvisionalCost
    follower: LogFollower | None = None


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

    def __post_init__(self):
        self._config_error: str | None = None
        try:
            self.config: HostConfig = load_host_config(environ=self.environ)
        except CONFIG_ERRORS as error:
            # A broken file is reported in every snapshot, never fatal to the monitor.
            self._config_error = _config_message(error)
            self.config = HostConfig(path=config_path(self.environ), loaded=False)
        self.locations = self._resolve()
        self.history_store = HistoryStore(self.locations["results_repo"].path)
        self._history: list[RunSummary] = []
        self._history_at = float("-inf")
        self._live: dict[str, _Live] = {}
        self._records = RecordCache()
        self._codex_readings: dict[str, tuple[float, UsageReading | None]] = {}
        self._repo = RepoFreshness(None, None)

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

    def _codex_reading(self, login: str) -> UsageReading | None:
        checked = self._codex_readings.get(login)
        if checked is None or time.monotonic() - checked[0] >= CODEX_READING_SECONDS:
            checked = (time.monotonic(), live_codex_reading(self.path("state_root"), login))
            self._codex_readings[login] = checked
        return checked[1]

    def _profiles(
        self, profiles: list[ProfileStatus], history: list[RunSummary], now: datetime
    ) -> list[ProfileView]:
        readings: dict[str, list[UsageReading]] = defaultdict(list)
        costs: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
        recorded = set()
        for summary in history:
            recorded.add(summary.run_id)
            login = _canonical_login(summary.login_profile, profiles)
            if login is None:
                continue
            costs[login].extend(summary.request_costs)
            if summary.usage_reading is not None:
                readings[login].append(summary.usage_reading)
        holder = {}
        for run_id, entry in self._live.items():
            login = entry.run.login_profile
            if login is None:
                continue
            holder[login] = run_id
            if run_id not in recorded:
                costs[login].extend(
                    (row.timestamp_ms, row.usd)
                    for row in entry.cost.requests
                    if row.usd is not None
                )
            if entry.follower is not None and entry.follower.reading is not None:
                readings[login].append(entry.follower.reading)
            if entry.run.provider == "codex" and entry.run.stage is Stage.RUNNING:
                reading = self._codex_reading(login)
                if reading is not None:
                    readings[login].append(reading)
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

    def snapshot(self) -> MonitorSnapshot:
        now = self.clock()
        containers, docker_error = self.docker()
        held = held_locks(self.proc_locks)
        profiles = login_profiles(self.path("state_root"), held)
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
        views = [
            RunView(
                run,
                estimated_percent(run, history, now)
                if run.stage not in (Stage.NEEDS_RECOVER, Stage.UNKNOWN)
                else None,
                self._live[run.run_id].cost.total if run.native_telemetry else None,
                self._live[run.run_id].cost.unpriced,
                tuple(
                    (row.timestamp_ms, row.usd)
                    for row in self._live[run.run_id].cost.requests
                    if row.usd is not None
                ),
            )
            for run in runs
        ]
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
            profiles=self._profiles(profiles, history, now),
            counts=counts,
            repo=self._repo,
            exclusion_error=self.history_store.exclusion_error,
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

    def workspace(self, run_id: str) -> WorkspaceView:
        """The run's snapshot timeline and the agent's commits, when this host has them."""
        return workspace_view(self.run_dir(run_id))

    def record_detail(self, summary: RunSummary) -> RecordDetail | None:
        """Requests, cost breakdown and failure facts from a recorded run's Run Record."""
        return record_detail(summary.path)

    def provisional_requests(self, run_id: str):
        entry = self._live.get(run_id)
        return entry.cost.requests if entry is not None else []

    def close(self) -> None:
        for entry in self._live.values():
            if entry.follower is not None:
                entry.follower.stop()
        self._live.clear()
