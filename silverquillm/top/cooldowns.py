"""The monitor's Cooldown writes, set from the LOGINS pane's keys.

It goes through the same file and validation as ``silverquillm login cooldown`` and touches
nothing else of the slot (RUN-MONITORING.md, Command and scope).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from silverquillm.karn.cooldowns import end_in_force_after, extend_hold
from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_pool import enrolled_slots, logins_root

STEP = timedelta(hours=1)
"""Each ``t`` holds the slot this much longer."""
GRACE = timedelta(seconds=10)
"""``c`` ends the Cooldowns in force this long from now rather than at once."""
WRITE_WAIT = 2.0
"""Seconds a key waits for another writer of the schedule before reporting it busy, so a
stalled ``login cooldown`` never freezes the monitor."""


def _slot_directory(state_root: Path, plugin_id: str, slot: str) -> Path:
    pool = logins_root(state_root) / plugin_id
    if slot not in enrolled_slots(pool, plugin_id):
        raise KarnError("login_slot_not_enrolled")
    return pool / slot


def lengthen(state_root: Path, plugin_id: str, slot: str, *, now: datetime) -> datetime:
    """Hold the slot one more ``STEP``; returns when its hold on every run now ends."""
    return extend_hold(_slot_directory(state_root, plugin_id, slot), STEP, now=now, wait=WRITE_WAIT)


def end_soon(state_root: Path, plugin_id: str, slot: str, *, now: datetime) -> datetime | None:
    """End the slot's Cooldowns in force after ``GRACE``, leaving those still to come; None,
    writing nothing, when none is in force."""
    return end_in_force_after(
        _slot_directory(state_root, plugin_id, slot), GRACE, now=now, wait=WRITE_WAIT
    )
