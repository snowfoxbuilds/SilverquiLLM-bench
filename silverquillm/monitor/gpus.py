"""This host's GPU Slots as the monitor shows them, read without taking any GPU Slot's lock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from silverquillm.karn.cooldowns import Cooldown, read_schedule
from silverquillm.karn.model_server import (
    GpuReading,
    gpu_slots,
    readable_gpu_schedule_dir,
    scheduled_gpu_slot_values,
    slot_unusable,
)

from .live import LiveRun, Stage
from .locks import lock_held


@dataclass(frozen=True)
class GpuSlotStatus:
    value: str | None
    """The slot's ``CUDA_VISIBLE_DEVICES``; None for a host's one unpinned slot."""
    held: bool | None
    """Whether a run holds the slot's lock; None when the lock table is unavailable."""
    busy: str | None
    """Why another job keeps the slot busy (``compute_process``, ``memory_used``), or None."""
    gpus: tuple[dict[str, Any], ...] | None
    """The slot's GPUs from ``nvidia-smi``; None, with ``gpus_reason``, when unread."""
    gpus_reason: str | None = None
    run_id: str | None = None
    """The live run whose server is on this slot, when the slot is held."""
    unusable: str | None = None
    """Why no run can use the slot, as admission judges it: a GPU ``nvidia-smi`` does not list,
    or a lock file this user cannot open."""
    cooldowns: tuple[Cooldown, ...] = ()
    """The slot's Cooldown Schedule: every Cooldown not yet ended, soonest first."""
    cooldown_until: datetime | None = None
    """When the last Cooldown in force ends; None when none is in force."""
    next_cooldown: datetime | None = None
    """When the next Cooldown starts, while none is in force."""

    @property
    def state(self) -> str:
        """One word, most blocking first; a held slot reads held whatever else is true, since
        a Cooldown never takes a slot from the run holding it."""
        if self.held:
            return "held"
        if self.unusable is not None:
            return "unusable"
        if self.cooldown_until is not None:
            return "cooldown"
        if self.busy is not None:
            return "busy"
        if self.held is None:
            return "unknown"
        return "free"


def _holder(value: str | None, runs: list[LiveRun]) -> str | None:
    """The run whose server is live on the slot: one staging or running. A run that is grading
    or recording has stopped its server and released the slot."""
    for run in runs:
        serving = run.stage in (Stage.STARTING, Stage.RUNNING)
        if run.model_server and run.gpu_slot == value and serving:
            return run.run_id
    return None


@dataclass(frozen=True)
class OrphanedSchedule:
    """A Cooldown Schedule kept for a GPU Slot value ``gpu_slots`` no longer lists: it holds
    back nothing, and stays only until the operator removes it."""

    value: str
    cooldowns: tuple[Cooldown, ...]


def _schedule(directory: Path | None, now: datetime):
    """The schedule, when its Cooldowns in force end, and when the next one starts."""
    if directory is None:
        return (), None, None
    schedule = tuple(read_schedule(directory, now=now))
    forced = [c.end for c in schedule if c.in_force(now)]
    upcoming = None if forced else min((c.start for c in schedule), default=None)
    return schedule, max(forced, default=None), upcoming


def gpu_slot_statuses(
    state_root: Path | None,
    configured: tuple[str, ...] | None,
    held,
    reading: GpuReading,
    runs: list[LiveRun],
    *,
    now: datetime | None = None,
) -> list[GpuSlotStatus]:
    """Every GPU Slot in config order; the held state comes from the kernel's lock table."""
    if state_root is None:
        return []
    moment = now or datetime.now(UTC)
    statuses = []
    for slot in gpu_slots(state_root, configured):
        locked = lock_held(slot.lock_path, held, follow_symlinks=True)
        gpus = slot.gpus(reading)
        schedule, until, upcoming = _schedule(slot.schedule_dir, moment)
        statuses.append(
            GpuSlotStatus(
                slot.value,
                locked,
                slot.busy(reading),
                None if gpus is None else tuple(gpus),
                reading.reason if gpus is None else None,
                _holder(slot.value, runs) if locked else None,
                slot_unusable(slot, reading),
                schedule,
                until,
                upcoming,
            )
        )
    return statuses


def orphaned_gpu_schedules(
    state_root: Path | None, configured: tuple[str, ...] | None, *, now: datetime | None = None
) -> list[OrphanedSchedule]:
    """Schedules with Cooldowns not yet ended for GPU Slot values ``gpu_slots`` does not list,
    every one of them on a host that lists none."""
    if state_root is None:
        return []
    moment = now or datetime.now(UTC)
    listed = set(configured or ())
    orphans = []
    for value in scheduled_gpu_slot_values(state_root):
        if value in listed:
            continue
        directory = readable_gpu_schedule_dir(state_root, value)
        schedule = () if directory is None else tuple(read_schedule(directory, now=moment))
        if schedule:
            orphans.append(OrphanedSchedule(value, schedule))
    return orphans
