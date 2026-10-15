"""One monitor snapshot as a JSON document: what ``top`` shows, for an agent without a terminal.

It is built from the same ``MonitorSnapshot`` the dashboard draws, so the run stage rules
(RUN-MONITORING.md, Run stages) are never restated here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .pools import ProfileStatus
from .queue import QueuedBatch
from .snapshot import MonitorSnapshot, ProfileView, RunView

SCHEMA_VERSION = 1


def _time(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _path(value: Path | None) -> str | None:
    return str(value) if value is not None else None


def _login_state(status: ProfileStatus) -> str:
    """One word for the slot, most blocking first: a pending settlement outranks the rest."""
    if status.pending:
        return "pending"
    if status.busy is None:
        return "unknown"
    if status.busy:
        return "busy"
    if status.cooldown_until is not None:
        return "cooldown"
    return "free"


def _batch_entries(snapshot: MonitorSnapshot) -> dict[str, tuple[str, int] | None]:
    """Each run's batch and entry: from the retained state files first, so a run keeps its
    batch after the Batch TOML is gone; an ambiguous run stays unknown (``None``)."""
    entries: dict[str, tuple[str, int] | None] = {
        run_id: (batch.batch, index)
        for batch in snapshot.queued
        for index, run_id in enumerate(batch.run_ids)
    }
    entries.update(snapshot.batch_runs)
    return entries


def _run(view: RunView, batches: dict[str, tuple[str, int] | None], now: datetime) -> dict:
    run = view.run
    batch, entry = batches.get(run.run_id) or (None, None)
    container = run.container
    return {
        "run_id": run.run_id,
        "stage": run.stage.value,
        "reasons": list(run.reasons),
        "batch": batch,
        "batch_entry": entry,
        "benchmark": run.benchmark,
        "construct": run.construct,
        "candidate_hash": run.candidate_hash,
        "model": run.candidate.model,
        "effort": run.candidate.effort,
        "login_profile": run.login_profile,
        "provider": run.provider,
        "budget_seconds": run.budget_seconds,
        "started_at": _time(run.started_at),
        "elapsed_seconds": run.elapsed_seconds(now),
        "container": None
        if container is None
        else {
            "name": container.name,
            "running": container.running,
            "started_at": _time(container.started_at),
            "finished_at": _time(container.finished_at),
        },
        "run_dir": _path(run.run_dir),
        "estimated_percent": view.estimated_percent,
        "estimated_cost_usd": _decimal(view.cost),
        "cost_recorded": view.cost_recorded,
        "record_run_id": run.record.run_id if run.record is not None else None,
    }


def _batch(batch: QueuedBatch) -> dict:
    return {
        "batch": batch.batch,
        "status": batch.status,
        "error": batch.error,
        "not_before": _time(batch.not_before),
        "started": batch.started,
        "total": batch.total,
        "run_ids": list(batch.run_ids),
        "pending": [
            {
                "index": run.index,
                "benchmark": run.benchmark,
                "construct": run.construct,
                "budget_seconds": run.budget_seconds,
            }
            for run in batch.runs
        ],
    }


def _login(view: ProfileView) -> dict:
    status = view.status
    weekly = view.weekly
    return {
        "login_profile": status.ref,
        "provider": status.provider,
        "state": _login_state(status),
        "busy": status.busy,
        "pending": status.pending,
        "pending_run": status.pending_run,
        "cooldown_until": _time(status.cooldown_until),
        "run_id": view.run_id,
        "weekly_usage_percent": weekly.percent if weekly is not None else None,
        "weekly_usage_estimated": weekly.estimated if weekly is not None else None,
        "weekly_resets_at": _time(weekly.resets_at) if weekly is not None else None,
    }


def snapshot_document(snapshot: MonitorSnapshot) -> dict:
    batches = _batch_entries(snapshot)
    return {
        "schema_version": SCHEMA_VERSION,
        "taken_at": _time(snapshot.taken_at),
        "host_label": snapshot.host_label,
        "locations": {
            key: {"path": _path(location.path), "source": location.source}
            for key, location in snapshot.locations.items()
        },
        "config_file": _path(snapshot.config_file),
        "errors": {
            "config": snapshot.config_error,
            "docker": snapshot.docker_error,
            "exclusions": snapshot.exclusion_error,
        },
        "dispatch": snapshot.dispatch,
        "ledger": {"status": snapshot.ledger, "error": snapshot.ledger_error},
        "counts": {
            "queued": snapshot.counts.queued,
            "live": snapshot.counts.live,
            "finished_recent": snapshot.counts.finished_recent,
            "finished_total": snapshot.counts.finished_total,
        },
        "runs": [_run(view, batches, snapshot.taken_at) for view in snapshot.running],
        "queue": [_batch(batch) for batch in snapshot.queued],
        "logins": [_login(view) for view in snapshot.profiles],
    }
