"""The monitor's Usage Limit writes, from the capacity view's ``L`` form.

They go through the same code as ``silverquillm login limit``: setting a limit checks it at
once, and the check may write a ``usage-limit`` Cooldown (RUN-MONITORING.md, Command and
scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.host_config import HostConfig
from silverquillm.karn.cooldowns import Cooldown
from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_admin import PROVIDER_OF
from silverquillm.karn.usage_limit import (
    UsageLimit,
    clear_limit,
    limit_profile,
    read_limit,
    usage_limit,
)
from silverquillm.monitor import MonitorSnapshot, UsageReading

from . import cooldowns
from .cooldowns import slot_directory

ESTIMATED_FROM = ("runs_dir", "results_repo", "bench_root")


@dataclass(frozen=True)
class Estimate:
    """What the monitor estimated one profile's usage from, taken on the UI thread from the
    snapshot shown, so the check off it sees the figure the operator saw: the locations the
    monitor resolved, flags included, its configuration and host label, and the live
    readings it keeps for the profile, with their own reset times."""

    locations: dict[str, Path | None]
    config: HostConfig
    host_label: str | None
    readings: tuple[UsageReading, ...]


def estimate(snapshot: MonitorSnapshot, config: HostConfig, plugin_id: str, slot: str) -> Estimate:
    def path(key: str) -> Path | None:
        location = snapshot.locations.get(key)
        return location.path if location is not None else None

    readings = next(
        (
            view.observed
            for view in snapshot.profiles
            if (view.status.plugin_id, view.status.slot) == (plugin_id, slot)
        ),
        (),
    )
    return Estimate(
        {key: path(key) for key in ESTIMATED_FROM}, config, snapshot.host_label, readings
    )


class Unchecked(Exception):
    """The limit is saved, but the check that should follow it could not complete."""


def ceilings(weekly: str, fable: str) -> UsageLimit | None:
    """The limit a form describes, ``80`` or ``80%`` per ceiling; None when both are empty,
    which clears the limit."""

    def percent(text: str) -> float | None:
        text = text.strip().removesuffix("%").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            raise KarnError("invalid_usage_limit") from None

    weekly_percent, fable_percent = percent(weekly), percent(fable)
    if weekly_percent is None and fable_percent is None:
        return None
    return usage_limit(weekly_percent, fable_percent)


def set_and_check(
    state_root: Path,
    plugin_id: str,
    slot: str,
    limit: UsageLimit,
    *,
    now: datetime,
    estimated: Estimate,
) -> list[Cooldown]:
    """Set the profile's limit and check it, as ``login limit`` does, against what the
    monitor ``estimated`` from; returns the Cooldowns the check wrote. It reads the host's
    history, so the monitor calls it off the UI thread, and it waits no longer than any other
    key for another writer of the schedule.

    Raises ``Unchecked`` when the limit was saved but its check failed: the limit stays."""
    directory = slot_directory(state_root, plugin_id, slot)
    provider = PROVIDER_OF[plugin_id]
    if limit.fable_percent is not None and provider != "claude":
        raise KarnError("fable_limit_claude_only")
    try:
        return limit_profile(
            directory,
            f"{plugin_id}/{slot}",
            provider,
            limit,
            state_root=state_root,
            now=now,
            locations=estimated.locations,
            readings=estimated.readings,
            config=estimated.config,
            host_label=estimated.host_label,
            wait=cooldowns.WRITE_WAIT,
        )
    except Exception as error:
        if read_limit(directory) == limit:
            raise Unchecked(error) from error
        raise


def clear(state_root: Path, plugin_id: str, slot: str) -> bool:
    """Remove the profile's limit; returns whether it had one."""
    return clear_limit(slot_directory(state_root, plugin_id, slot))
