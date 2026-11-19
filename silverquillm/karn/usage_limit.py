"""Usage Limits: a Login Profile's ceiling on its Estimated Weekly Usage, and on its Fable limit.

A limit is one small file (``usage-limit.json``) beside the profile's stored login. It is
checked when a run releases the profile, when a recovery settles a login, and whenever the
operator sets one; at or above a ceiling, the check adds a ``usage-limit`` Cooldown to the
profile's Cooldown Schedule until that window's next reset. The estimate is the monitor's
own (``silverquillm.monitor.usage``), so the figure the operator sees is the one that trips.

A limit gates only new runs; nothing here touches a stored login, a lock, or a run. An
unreadable limit is no limit, and a failed check never fails the run or recovery it follows.
"""

from __future__ import annotations

import contextlib
import math
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from .cooldowns import HORIZON, Cooldown, cooldown, edit_schedule
from .definition import KarnError, canonical, read_regular, strict_json
from .login import write_private

if TYPE_CHECKING:
    from silverquillm.monitor.history import UsageReading
    from silverquillm.monitor.usage import ProfileUsage

LIMIT_FILE = "usage-limit.json"
LIMIT_SIZE = 4096
WEEK = timedelta(days=7)
"""A weekly window resets every seven days, so a passed reset predicts the next ones."""
SCHEDULE_WAIT = 10.0
"""How long a run or recovery waits on another writer of the Cooldown Schedule before it
gives up the check, so a stalled writer never keeps it from releasing the login."""

_UNREADABLE = (KarnError, OSError, KeyError, TypeError, ValueError, OverflowError, RecursionError)


@dataclass(frozen=True)
class UsageLimit:
    weekly_percent: float | None = None
    fable_percent: float | None = None
    """Claude's Fable limit only; it holds back only Fable runs."""

    def document(self) -> dict:
        return {"weekly_percent": self.weekly_percent, "fable_percent": self.fable_percent}


def ceiling(value: object) -> float | None:
    """A ceiling in percent, above 0 and at most 100; None stays unset."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise KarnError("invalid_usage_limit")
    value = float(value)
    if not math.isfinite(value) or not 0 < value <= 100:
        raise KarnError("invalid_usage_limit")
    return value


def usage_limit(weekly: object = None, fable: object = None) -> UsageLimit:
    """A new limit, refused unless it sets at least one ceiling in (0, 100]."""
    limit = UsageLimit(ceiling(weekly), ceiling(fable))
    if limit.weekly_percent is None and limit.fable_percent is None:
        raise KarnError("usage_limit_empty")
    return limit


def read_limit(directory: Path) -> UsageLimit | None:
    """The profile's Usage Limit; None when it has none or it cannot be read."""
    path = Path(directory) / LIMIT_FILE
    try:
        if not (path.exists() or path.is_symlink()):
            return None
        document = strict_json(read_regular(path, limit=LIMIT_SIZE))
        if not isinstance(document, dict) or document.get("format") != 1:
            raise ValueError("unknown format")
        return usage_limit(document.get("weekly_percent"), document.get("fable_percent"))
    except _UNREADABLE:
        return None


def set_limit(directory: Path, limit: UsageLimit, *, now: datetime) -> UsageLimit:
    document = {"format": 1, **limit.document(), "set_at": _stamp(now)}
    write_private(Path(directory) / LIMIT_FILE, canonical(document))
    return limit


def clear_limit(directory: Path) -> bool:
    """Remove the profile's Usage Limit; returns whether it had one."""
    path = Path(directory) / LIMIT_FILE
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def next_reset(reading: UsageReading | None, now: datetime) -> datetime:
    """When the reading's window next resets: its own reset while that is still to come,
    else that reset moved on in seven-day steps to the first one still to come; with no
    reading at all, seven days from now."""
    if reading is None:
        return now + WEEK
    reset = reading.resets_at
    if reset > now:
        return reset
    return reset + WEEK * ((now - reset) // WEEK + 1)


def due_cooldowns(limit: UsageLimit, usage: ProfileUsage, *, now: datetime) -> list[Cooldown]:
    """The Cooldowns a limit asks for at ``now``: one for every run while the weekly estimate
    is at or above its ceiling, and one for Fable runs while the Fable limit's is.

    Each is built on its own, so one that cannot be built never costs the other. A reset
    more than ``HORIZON`` ahead is no usable reading, so its Cooldown lasts seven days from
    now, as with no reading at all.
    """
    due = []
    for scope, ceiling_percent, estimate, reading in (
        ("all", limit.weekly_percent, usage.weekly, usage.weekly_reading),
        ("fable", limit.fable_percent, usage.fable, usage.fable_reading),
    ):
        if ceiling_percent is None or estimate is None or estimate.percent < ceiling_percent:
            continue
        try:
            end = next_reset(reading, now)
            if end - now > HORIZON:
                end = now + WEEK
            due.append(cooldown(now, end, now=now, scope=scope, source="usage-limit"))
        except (KarnError, TypeError, ValueError, OverflowError):
            continue
    return due


def apply_limit(
    directory: Path,
    limit: UsageLimit,
    usage: ProfileUsage,
    *,
    now: datetime,
    wait: float | None = None,
) -> list[Cooldown]:
    """Write the Cooldowns ``limit`` asks for, unless a ``usage-limit`` Cooldown of the same
    scope is already in force; returns those written. ``wait`` bounds the wait on another
    writer of the schedule, as ``edit_schedule`` does."""
    due = due_cooldowns(limit, usage, now=now)
    if not due:
        return []
    written: list[Cooldown] = []

    def tripped(cooldowns: list[Cooldown]) -> list[Cooldown]:
        held = {c.scope for c in cooldowns if c.source == "usage-limit" and c.in_force(now)}
        written.extend(c for c in due if c.scope not in held)
        return [*cooldowns, *written]

    edit_schedule(directory, tripped, now=now, wait=wait)
    return written


def run_readings(measurement: object, bound: datetime) -> list[UsageReading]:
    """The weekly and Fable readings of a run's ``subscription_usage`` measurement, taken by
    ``bound`` at the latest, as the run's record would show them."""
    from silverquillm.monitor.history import FABLE, WEEKLY, usage_reading

    if not isinstance(measurement, dict):
        return []
    weekly = usage_reading(measurement.get("value"), bound, WEEKLY)
    fable = usage_reading(measurement.get("fable"), bound, FABLE)
    if fable is not None and fable.provider != "claude":
        fable = None
    return [reading for reading in (weekly, fable) if reading is not None]


def check_usage_limit(
    directory: Path,
    login: str,
    provider: str,
    *,
    state_root: Path,
    runs_dir: Path | None,
    results_repo: Path | None,
    readings: Iterable[UsageReading] = (),
    execution=None,
    now: datetime | None = None,
    config=None,
    wait: float | None = None,
    bench_root: Path | None = None,
    host_label: str | None = None,
) -> list[Cooldown]:
    """Check one profile's Usage Limit against this host's estimate, writing the Cooldowns
    it asks for. A profile without a limit costs nothing: no estimate is made.

    ``execution`` (an ``ExecutionSpend``) is the reconciled spend of the run just ending, in
    place of whatever its telemetry or records would charge. ``host_label`` is the label a
    caller has already resolved, as the monitor has; without one it is resolved from
    ``config``."""
    limit = read_limit(directory)
    if limit is None:
        return []
    from silverquillm.host_config import load_host_config
    from silverquillm.monitor.usage import estimate_profile_usage

    from .provenance import host_label as resolve_host_label

    config = load_host_config() if config is None else config
    now = now or datetime.now(UTC)
    usage = estimate_profile_usage(
        login,
        provider,
        rates=config.usage_rates,
        host_label=host_label if host_label is not None else resolve_host_label(config=config)[0],
        state_root=Path(state_root),
        runs_dir=Path(runs_dir) if runs_dir is not None else None,
        results_repo=Path(results_repo) if results_repo is not None else None,
        bench_root=Path(bench_root) if bench_root is not None else None,
        readings=readings,
        execution=execution,
        now=now,
    )
    return apply_limit(directory, limit, usage, now=now, wait=wait)


def host_locations(state_root: Path) -> dict:
    """Where this host's runs and records are, for a check made outside any run: the state
    root given, and the run directory and Results Repo its configuration names, if any."""
    from silverquillm.host_config import resolve_location

    def location(key):
        try:
            return resolve_location(key).path
        except Exception:  # noqa: BLE001 -- an unresolved location only adds no records.
            return None

    return {
        "state_root": Path(state_root),
        "runs_dir": location("runs_dir"),
        "results_repo": location("results_repo"),
    }


def limit_profile(
    directory: Path,
    login: str,
    provider: str,
    limit: UsageLimit,
    *,
    state_root: Path,
    now,
    locations: Mapping[str, Path | None] | None = None,
    readings: Iterable[UsageReading] = (),
    config=None,
    host_label: str | None = None,
    wait: float | None = None,
) -> list[Cooldown]:
    """Set one profile's Usage Limit and check it at once, from the same pieces `login limit`
    uses; returns the Cooldowns the check wrote. The limit stays set if the check fails.

    A caller that has already estimated the profile's usage, as the monitor has, passes what
    it estimated from, so the check sees the figure it shows: ``locations`` (its
    ``runs_dir``, ``results_repo`` and ``bench_root``, in place of those the configuration
    names), the live ``readings`` only it holds, its ``config`` and its ``host_label``.
    ``wait`` bounds the wait on another writer of the schedule, as ``edit_schedule`` does."""
    set_limit(directory, limit, now=now)
    if locations is None:
        where = host_locations(state_root)
    else:
        where = {
            "state_root": Path(state_root),
            "runs_dir": locations.get("runs_dir"),
            "results_repo": locations.get("results_repo"),
            "bench_root": locations.get("bench_root"),
        }
    return check_usage_limit(
        directory,
        login,
        provider,
        now=now,
        readings=readings,
        config=config,
        host_label=host_label,
        wait=wait,
        **where,
    )


def check_quietly(
    directory: Path,
    login: str,
    provider: str | None,
    *,
    readings: Callable[[], Iterable[UsageReading]] = tuple,
    spend: Callable[[], object] | None = None,
    **arguments,
) -> None:
    """Check the limit, reporting any failure on stderr: a failed check never fails, nor
    holds up past ``SCHEDULE_WAIT``, the run or the recovery it follows; it only leaves the
    profile without a new Cooldown.

    ``readings`` gathers the caller's own readings, and ``spend`` the reconciled spend of
    the run just ending (an ``ExecutionSpend``); each is called only for a profile that has a
    limit, so a run on a profile without one reads nothing more. Spend that cannot be
    gathered is reported and the check goes on with what the host's records and telemetry
    show.
    """
    if provider is None:
        return
    try:
        if read_limit(directory) is None:
            return
        found = list(readings())
        execution = None
        if spend is not None:
            try:
                execution = spend()
            except Exception as error:  # noqa: BLE001 -- the check goes on without it.
                _report(f"{login}: usage_limit_spend_unavailable: {_reason(error)}")
        written = check_usage_limit(
            directory,
            login,
            provider,
            readings=found,
            execution=execution,
            wait=SCHEDULE_WAIT,
            **arguments,
        )
    except Exception as error:  # noqa: BLE001 -- a failed check must never fail the run.
        _report(f"{login}: usage_limit_check_failed: {_reason(error)}")
        return
    for held in written:
        scope = "Fable runs" if held.scope == "fable" else "every run"
        _report(f"{login}: Usage Limit reached; {scope} held until {_stamp(held.end)}")


def run_spend(execution_id: str, measurements: dict, model: str | None):
    """The ``ExecutionSpend`` a run's measurements will charge once its record exists."""
    from silverquillm.monitor.usage import execution_spend

    return execution_spend(execution_id, measurements, model)


def has_limit(directory: Path) -> bool:
    """Whether the profile has a Usage Limit; one that cannot be read is none."""
    try:
        return read_limit(directory) is not None
    except Exception:  # noqa: BLE001 -- an unreadable limit holds nothing back.
        return False


def _reason(error: Exception) -> str:
    return str(error) if isinstance(error, KarnError) else type(error).__name__


def _report(message: str) -> None:
    # Nor may reporting it, on a closed or broken stderr.
    with contextlib.suppress(Exception):
        print(message, file=sys.stderr)
