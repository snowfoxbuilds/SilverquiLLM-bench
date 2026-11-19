"""The monitor's Cooldown writes, from the LOGINS pane's keys and the capacity view's forms.

They go through the same files and validation as ``silverquillm login cooldown`` and
``silverquillm gpu cooldown`` and touch nothing else of the slot (RUN-MONITORING.md, Command
and scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from silverquillm.karn.cooldowns import (
    Cooldown,
    cooldown,
    edit_schedule,
    edited,
    end_in_force_after,
    extend_hold,
    parse_time,
)
from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_pool import enrolled_slots, logins_root
from silverquillm.karn.model_server import writable_gpu_schedule_dir

STEP = timedelta(hours=1)
"""Each ``t`` holds the slot this much longer."""
GRACE = timedelta(seconds=10)
"""``c`` ends the Cooldowns in force this long from now rather than at once."""
WRITE_WAIT = 2.0
"""Seconds a key waits for another writer of the schedule before reporting it busy, so a
stalled ``login cooldown`` never freezes the monitor."""


@dataclass(frozen=True)
class Target:
    """A Login Profile (``plugin_id`` and slot) or a GPU Slot (its value, no ``plugin_id``)
    whose Cooldown Schedule the monitor writes."""

    plugin_id: str | None
    name: str
    orphaned: bool = False
    """A GPU Slot value ``gpu_slots`` no longer lists: its schedule holds back nothing."""

    @property
    def gpu(self) -> bool:
        return self.plugin_id is None

    @property
    def label(self) -> str:
        return f"gpu {self.name}" if self.gpu else f"{self.plugin_id}/{self.name}"


def slot_directory(state_root: Path, plugin_id: str, slot: str) -> Path:
    pool = logins_root(state_root) / plugin_id
    if slot not in enrolled_slots(pool, plugin_id):
        raise KarnError("login_slot_not_enrolled")
    return pool / slot


def _directory(state_root: Path, target: Target) -> Path:
    """Where the target's schedule is written; a GPU Slot's through the CLI's own refusal of
    a symlinked or non-directory path, so no write ever lands outside ``gpu-slots/``."""
    if not target.gpu:
        return slot_directory(state_root, target.plugin_id, target.name)
    return writable_gpu_schedule_dir(state_root, target.name)


def lengthen(state_root: Path, plugin_id: str, slot: str, *, now: datetime) -> Cooldown:
    """Hold the slot one more ``STEP``; returns the Cooldown that now holds it, whose scope
    says whether that hold is on every run or on Fable runs only."""
    return extend_hold(slot_directory(state_root, plugin_id, slot), STEP, now=now, wait=WRITE_WAIT)


def end_soon(state_root: Path, plugin_id: str, slot: str, *, now: datetime) -> datetime | None:
    """End the slot's Cooldowns in force after ``GRACE``, leaving those still to come; None,
    writing nothing, when none is in force."""
    return end_in_force_after(
        slot_directory(state_root, plugin_id, slot), GRACE, now=now, wait=WRITE_WAIT
    )


def window(
    start: str,
    end: str,
    *,
    now: datetime,
    fable: bool = False,
    note: str = "",
    source: str = "operator",
    extend: bool = False,
    keep: Cooldown | None = None,
    shown=None,
) -> Cooldown:
    """The Cooldown a form describes, read as ``login cooldown`` reads its times: an empty
    start is now, and an offset end counts from the start. ``extend`` is a new GPU Slot
    Cooldown's choice to extend while its GPUs are used outside the bench (``--no-extend``
    when false).

    Editing ``keep``, a time left as ``shown`` printed it keeps its exact instant, so a form
    that changes only the note never moves the window by the seconds it does not show.
    """
    if keep is not None and shown is not None and start.strip() == shown(keep.start):
        begins = keep.start
    else:
        begins = parse_time(start, now=now) if start.strip() else now
    if not end.strip():
        raise KarnError("cooldown_end_needed")
    if keep is not None and shown is not None and end.strip() == shown(keep.end):
        ends = keep.end
    else:
        ends = parse_time(end, now=now, base=begins)
    return cooldown(
        begins,
        ends,
        now=now,
        scope="fable" if fable else "all",
        source=source,
        note=note.strip() or None,
        extend=extend,
    )


def add(state_root: Path, target: Target, new: Cooldown, *, now: datetime) -> Cooldown:
    """Add one Cooldown beside those already scheduled; an orphaned schedule takes none."""
    if target.orphaned:
        raise KarnError("gpu_slot_not_listed")
    directory = _directory(state_root, target)
    edit_schedule(directory, lambda cooldowns: [*cooldowns, new], now=now, wait=WRITE_WAIT)
    return new


def replace(
    state_root: Path, target: Target, old: Cooldown, new: Cooldown, *, now: datetime
) -> Cooldown:
    """Put ``new`` in place of ``old``, refused when ``old`` has ended, been removed or been
    extended since the form opened, so an edit never turns into a second Cooldown.

    The edit is the operator's override: it keeps ``old``'s extension count but is never
    extended again, so an end deliberately moved is not pushed back out by a busy GPU.
    """
    if target.orphaned:
        raise KarnError("gpu_slot_not_listed")
    new = edited(new, extensions=old.extensions)

    def swap(cooldowns: list[Cooldown]) -> list[Cooldown]:
        if old not in cooldowns:
            raise KarnError("cooldown_no_longer_scheduled")
        return [new if entry == old else entry for entry in cooldowns]

    edit_schedule(_directory(state_root, target), swap, now=now, wait=WRITE_WAIT)
    return new


def remove(state_root: Path, target: Target, old: Cooldown, *, now: datetime) -> bool:
    """Remove one Cooldown, matched exactly, orphaned schedules' included; returns whether it
    was still there."""
    found: list[Cooldown] = []

    def without(cooldowns: list[Cooldown]) -> list[Cooldown]:
        found.extend(entry for entry in cooldowns if entry == old)
        return [entry for entry in cooldowns if entry != old]

    edit_schedule(_directory(state_root, target), without, now=now, wait=WRITE_WAIT)
    return bool(found)
