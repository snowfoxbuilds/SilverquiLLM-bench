"""Each Login Profile's Estimated Weekly Usage and Fable limit, from what a caller can see.

The monitor and the host's Usage Limit check share this estimator, so the figure shown is
the one that trips a Usage Limit (RUN-MONITORING.md, Estimated Weekly Usage). Records
supply most of the readings and spend; a caller adds what only it holds: the monitor its
live runs' readings and provisional costs, a runner the readings of the run it just ended.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from silverquillm.karn.cooldowns import is_fable

from .costs import ProvisionalCost
from .estimates import WeeklyUsage, newest_reading, weekly_usage
from .history import (
    FABLE,
    WEEKLY,
    HistoryStore,
    RunSummary,
    UsageReading,
    measured_request_costs,
)
from .live import RecordCache, live_runs
from .locks import PROC_LOCKS, held_locks
from .pools import ProfileStatus, login_profiles

Cost = tuple[int, Decimal]
"""``(timestamp_ms, usd)`` of one priced request."""


@dataclass(frozen=True)
class ExecutionSpend:
    """One execution's reconciled spend, which a caller holds before its record exists."""

    execution_id: str
    costs: tuple[Cost, ...]
    model: str | None


def execution_spend(execution_id: str, measurements: dict, model: str | None) -> ExecutionSpend:
    """The spend a run's measurements will charge once recorded: the requests its Run Cost's
    source prices, OTel and native evidence reconciled as in its record."""
    return ExecutionSpend(execution_id, measured_request_costs(measurements), model)


def canonical_login(login: str | None, profiles: Iterable[ProfileStatus]) -> str | None:
    """Records from before pools name only the slot, which kept its name when adopted."""
    if not login or "/" in login:
        return login
    matches = [profile.ref for profile in profiles if profile.slot == login]
    return matches[0] if len(matches) == 1 else login


def spend_rank(record: RunSummary, local: bool) -> tuple:
    """Which record of one execution counts. The record selected for a run directory on
    this host comes first, so its profile and its own view agree; among published records a
    stopped linked recovery reconciles its original."""
    recovered = record.recovery_of is not None and record.workspace_stopped is True
    return (local, recovered, record.run_date.timestamp() if record.run_date else 0.0)


def accountable(
    history: Iterable[RunSummary], host_label: str | None, cache: RecordCache
) -> list[RunSummary]:
    """This host's published records that pass the record's own validation and are filed
    under their own identity; history shows the rest but they charge nothing."""
    found = []
    for summary in history:
        if host_label is None or summary.host_label != host_label:
            continue
        record = cache.published(summary.path)
        if isinstance(record, RunSummary):
            found.append(record)
    return found


@dataclass
class UsageInputs:
    """The readings and spend each Login Profile's estimates are computed from."""

    readings: defaultdict[str, list[UsageReading]] = field(
        default_factory=lambda: defaultdict(list)
    )
    costs: defaultdict[str, list[Cost]] = field(default_factory=lambda: defaultdict(list))
    fable_costs: defaultdict[str, list[Cost]] = field(default_factory=lambda: defaultdict(list))
    """The Fable limit counts only Fable requests (``weekly_usage``, window ``fable``)."""
    executions: dict[str, tuple[str, RunSummary]] = field(default_factory=dict)
    """Each recorded execution's Login Profile and the one record whose spend counts."""

    @classmethod
    def from_records(
        cls,
        profiles: list[ProfileStatus],
        published: Iterable[RunSummary],
        local: Iterable[RunSummary],
        *,
        replacing: str | None = None,
    ) -> UsageInputs:
        """For each execution this host ran, its Login Profile and the one record whose spend
        counts, and every reading those records observed per Login Profile.

        ``published`` are this host's ``accountable`` records and ``local`` the record that
        applies to each of this host's run directories; any other record stays in history
        only. Only validated records count, so invalid evidence neither charges spend nor
        anchors usage.
        """
        inputs = cls()
        best: dict[str, tuple[tuple, str, RunSummary]] = {}
        both = [*((summary, False) for summary in published), *((s, True) for s in local)]
        for summary, local_copy in both:
            login = canonical_login(summary.login_profile, profiles)
            if login is None:
                continue
            for reading in (summary.usage_reading, summary.fable_usage_reading):
                if reading is not None:
                    inputs.readings[login].append(reading)
            rank = spend_rank(summary, local_copy)
            current = best.get(summary.execution_id)
            if current is None or rank > current[0]:
                best[summary.execution_id] = (rank, login, summary)
        inputs.executions = {key: (login, record) for key, (_, login, record) in best.items()}
        for execution, (login, record) in inputs.executions.items():
            if execution != replacing:
                inputs.add_costs(login, record.request_costs, record.candidate.model)
        return inputs

    def add_costs(self, login: str, costs: Iterable[Cost], model: str | None) -> None:
        costs = list(costs)
        self.costs[login].extend(costs)
        if is_fable(model):
            self.fable_costs[login].extend(costs)

    def add_reading(self, login: str, reading: UsageReading) -> None:
        self.readings[login].append(reading)


@dataclass(frozen=True)
class ProfileUsage:
    weekly: WeeklyUsage | None
    """None without a rate for the profile's provider."""
    fable: WeeklyUsage | None
    """Claude's Fable limit, once a reading of it has been seen for this profile."""
    weekly_reading: UsageReading | None
    """The newest reading of the weekly window, even once its reset has passed."""
    fable_reading: UsageReading | None
    """The newest reading of the Fable limit, even once its reset has passed."""


def profile_usage(
    login: str,
    provider: str,
    inputs: UsageInputs,
    rates: Mapping[str, Decimal],
    now: datetime,
) -> ProfileUsage:
    readings = inputs.readings[login]
    fable = None
    if any(r.window == FABLE for r in readings):
        fable = weekly_usage(
            login, provider, rates, readings, inputs.fable_costs[login], now, FABLE
        )
    return ProfileUsage(
        weekly_usage(login, provider, rates, readings, inputs.costs[login], now),
        fable,
        newest_reading(provider, readings, WEEKLY),
        newest_reading(provider, readings, FABLE),
    )


def estimate_profile_usage(
    login: str,
    provider: str,
    *,
    rates: Mapping[str, Decimal],
    host_label: str | None,
    state_root: Path | None,
    runs_dir: Path | None,
    results_repo: Path | None,
    bench_root: Path | None = None,
    readings: Iterable[UsageReading] = (),
    execution: ExecutionSpend | None = None,
    now: datetime,
    proc_locks: Path = PROC_LOCKS,
) -> ProfileUsage:
    """One Login Profile's estimates as the monitor would show them, without a monitor.

    It reads this host's records and the provisional spend of every unrecorded run in the
    run directory, as the monitor does; ``readings`` are live readings only the caller
    holds, such as those of the run it has just ended, whose record may not exist yet.
    Docker is not consulted, so a running container's live readings count only when passed.
    Each unrecorded run's events file is read once to its current length
    (``ProvisionalCost.read_snapshot``), so its whole spend counts as the monitor's does
    once caught up, however large the backlog.

    ``execution`` is the reconciled spend of one execution the caller has just ended, such
    as a run releasing its profile before its record exists: it replaces whatever that
    execution's records or provisional telemetry would charge, so it is never counted twice.
    """
    held = held_locks(proc_locks)
    profiles = login_profiles(state_root, held, now=now)
    login = canonical_login(login, profiles)
    cache = RecordCache()
    runs = live_runs(
        runs_dir,
        [],
        held,
        results_repo=results_repo,
        pending_logins={profile.pending_run for profile in profiles if profile.pending_run},
        cache=cache,
    )
    history = HistoryStore(results_repo, bench_root).runs()
    replacing = execution.execution_id if execution is not None else None
    inputs = UsageInputs.from_records(
        profiles,
        accountable(history, host_label, cache),
        cache.applicable_records(),
        replacing=replacing,
    )
    for run in runs:
        if run.login_profile != login or run.run_id in inputs.executions:
            continue
        if run.run_id == replacing:
            continue
        cost = ProvisionalCost(run.run_dir, run.telemetry_adapter)
        if run.native_telemetry:
            cost.read_snapshot()
        inputs.add_costs(
            login,
            ((row.timestamp_ms, row.usd) for row in cost.requests if row.usd is not None),
            run.candidate.model,
        )
    if execution is not None:
        inputs.add_costs(login, execution.costs, execution.model)
    for reading in readings:
        inputs.add_reading(login, reading)
    return profile_usage(login, provider, inputs, rates, now)
