"""This host's GPU Slots as the monitor shows them, read without taking any GPU Slot's lock."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from silverquillm.karn.model_server import GpuReading, gpu_slots, slot_unusable

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

    @property
    def state(self) -> str:
        """One word, most blocking first; a held slot reads held whatever else is true."""
        if self.held:
            return "held"
        if self.unusable is not None:
            return "unusable"
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


def gpu_slot_statuses(
    state_root: Path | None,
    configured: tuple[str, ...] | None,
    held,
    reading: GpuReading,
    runs: list[LiveRun],
) -> list[GpuSlotStatus]:
    """Every GPU Slot in config order; the held state comes from the kernel's lock table."""
    if state_root is None:
        return []
    statuses = []
    for slot in gpu_slots(state_root, configured):
        locked = lock_held(slot.lock_path, held, follow_symlinks=True)
        gpus = slot.gpus(reading)
        statuses.append(
            GpuSlotStatus(
                slot.value,
                locked,
                slot.busy(reading),
                None if gpus is None else tuple(gpus),
                reading.reason if gpus is None else None,
                _holder(slot.value, runs) if locked else None,
                slot_unusable(slot, reading),
            )
        )
    return statuses
