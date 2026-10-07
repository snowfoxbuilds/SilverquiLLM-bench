"""Estimated % of a live run and each Login Profile's Estimated Weekly Usage (RUN-MONITORING.md)."""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .history import RunSummary, UsageReading
from .live import LiveRun

LIVE_CAP = 99.0
WEEK = timedelta(days=7)


def estimated_percent(run: LiveRun, history: Iterable[RunSummary], now: datetime) -> float | None:
    """Elapsed container time over the median duration of comparable completed runs.

    Comparable runs share the benchmark and are completed and not excluded: the same
    Candidate Hash's when there are any, else the same Candidate display's.
    """
    elapsed = run.elapsed_seconds(now)
    if elapsed is None or run.benchmark is None:
        return None
    completed = [
        summary
        for summary in history
        if summary.benchmark == run.benchmark
        and summary.status == "completed"
        and summary.excluded is None
        and summary.duration_seconds
    ]
    same = [s for s in completed if run.candidate_hash and s.candidate_hash == run.candidate_hash]
    same = same or [s for s in completed if s.candidate.key == run.candidate.key]
    if not same:
        return None
    median = statistics.median(s.duration_seconds for s in same)
    return min(LIVE_CAP, 100.0 * elapsed / median)


@dataclass(frozen=True)
class WeeklyUsage:
    profile: str
    """The Login Profile, ``<plugin-id>/<slot>``."""
    percent: float
    estimated: bool
    """Shown with ``≈``: some or all of the value is Estimated Cost converted at the rate."""
    reading: UsageReading | None
    """The reading the value starts from, while its window has not reset."""

    @property
    def resets_at(self) -> datetime | None:
        return self.reading.resets_at if self.reading else None

    def reading_age(self, now: datetime) -> timedelta | None:
        moment = self.reading.effective_at if self.reading else None
        return now - moment if moment else None


def _spent(costs: Iterable[tuple[int, Decimal]], since: datetime | None) -> Decimal:
    floor = since.timestamp() * 1000 if since else float("-inf")
    return sum((usd for stamp, usd in costs if stamp > floor), Decimal(0))


def weekly_usage(
    profile: str,
    provider: str,
    rates: Mapping[str, Decimal],
    readings: Iterable[UsageReading],
    costs: Iterable[tuple[int, Decimal]],
    now: datetime,
) -> WeeklyUsage | None:
    """The profile's value per the spec's table; None without a rate for its provider.

    ``costs`` are ``(timestamp_ms, usd)`` of every request the profile served, from records
    and live runs alike; an Exclusion does not undo spend, so excluded runs count.
    """
    rate = rates.get(provider)
    if rate is None or rate <= 0:
        return None
    costs = list(costs)
    timed = [r for r in readings if r.provider == provider and r.effective_at is not None]
    newest = max(timed, key=lambda r: r.effective_at, default=None)
    if newest is not None and now < newest.resets_at:
        added = _spent(costs, newest.effective_at) / rate
        return WeeklyUsage(profile, newest.utilization_percent + float(added), added > 0, newest)
    since = newest.resets_at if newest is not None else now - WEEK
    return WeeklyUsage(profile, float(_spent(costs, since) / rate), True, None)
