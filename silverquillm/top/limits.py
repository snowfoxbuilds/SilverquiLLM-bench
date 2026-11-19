"""The monitor's Usage Limit writes, from the capacity view's ``L`` form.

They go through the same code as ``silverquillm login limit``: setting a limit checks it at
once, and the check may write a ``usage-limit`` Cooldown (RUN-MONITORING.md, Command and
scope).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from silverquillm.karn.cooldowns import Cooldown
from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_admin import PROVIDER_OF
from silverquillm.karn.usage_limit import UsageLimit, clear_limit, limit_profile, usage_limit

from .cooldowns import slot_directory


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
    state_root: Path, plugin_id: str, slot: str, limit: UsageLimit, *, now: datetime
) -> list[Cooldown]:
    """Set the profile's limit and check it, as ``login limit`` does; returns the Cooldowns
    the check wrote. It reads the host's history, so the monitor calls it off the UI thread."""
    directory = slot_directory(state_root, plugin_id, slot)
    provider = PROVIDER_OF[plugin_id]
    if limit.fable_percent is not None and provider != "claude":
        raise KarnError("fable_limit_claude_only")
    return limit_profile(
        directory, f"{plugin_id}/{slot}", provider, limit, state_root=state_root, now=now
    )


def clear(state_root: Path, plugin_id: str, slot: str) -> bool:
    """Remove the profile's limit; returns whether it had one."""
    return clear_limit(slot_directory(state_root, plugin_id, slot))
