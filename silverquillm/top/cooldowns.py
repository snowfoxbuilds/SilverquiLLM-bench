"""The monitor's one write: a Login Cooldown set from the status pane's keys.

It goes through the same file and validation as ``silverquillm login cooldown`` and touches
nothing else of the slot (RUN-MONITORING.md, Command and scope).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_cooldown import end_cooldown_after, extend_cooldown
from silverquillm.karn.login_pool import enrolled_slots, logins_root

STEP = timedelta(hours=1)
"""Each ``t`` holds the slot this much longer."""
GRACE = timedelta(seconds=10)
"""``c`` ends a cooldown this long from now rather than at once."""


def _slot_directory(state_root: Path, plugin_id: str, slot: str) -> Path:
    pool = logins_root(state_root) / plugin_id
    if slot not in enrolled_slots(pool, plugin_id):
        raise KarnError("login_slot_not_enrolled")
    return pool / slot


def lengthen(state_root: Path, plugin_id: str, slot: str, *, now: datetime) -> datetime:
    """Hold the slot one more ``STEP``; returns when its cooldown now ends."""
    return extend_cooldown(_slot_directory(state_root, plugin_id, slot), STEP, now=now)


def end_soon(state_root: Path, plugin_id: str, slot: str, *, now: datetime) -> datetime | None:
    """End the slot's cooldown after ``GRACE``; None, writing nothing, when it has none."""
    return end_cooldown_after(_slot_directory(state_root, plugin_id, slot), GRACE, now=now)
