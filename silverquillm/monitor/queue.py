"""Not-yet-started run specs of the batch queue, in the order the scheduler will run them."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.karn.batching import (
    LEDGER_FILENAME,
    load_batch,
    queue_order,
    read_ledger,
    read_state,
    stateless_status,
)
from silverquillm.karn.definition import KarnError

from ._read import read_json
from .candidates import CandidateDisplay, candidate_display

MAX_BATCH_FILE = 16 * 1024 * 1024


@dataclass(frozen=True)
class QueuedRun:
    index: int
    benchmark: str
    construct: str
    build_output: str
    budget_seconds: int
    candidate: CandidateDisplay


@dataclass(frozen=True)
class QueuedBatch:
    batch: str
    status: str
    """``pending``, ``running``, ``done``, ``needs_ack`` (no state, and not new),
    ``ledger_damaged`` (the queue ledger stops every dispatch), ``legacy`` or ``error``."""
    not_before: datetime | None
    started: int
    total: int
    runs: tuple[QueuedRun, ...]
    error: str | None = None

    @property
    def needs_ack(self) -> bool:
        return self.status == "needs_ack"


def _candidate(build_output: str, construct: str) -> CandidateDisplay:
    """The construct's built definition, read directly: no image is inspected to name it."""
    definition = None
    if "/" not in construct and not construct.startswith("."):
        definition = read_json(Path(build_output) / "constructs" / construct / "definition.json")
    return candidate_display(definition if definition is not None else {"name": construct})


def _unparseable(path: Path) -> bool:
    """A FIFO would block the poll and a huge file exhaust memory; neither is a batch file."""
    try:
        info = os.stat(path)
    except OSError:
        return False  # missing or a dangling link: the batch reader reports it
    return not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BATCH_FILE


def queued_batches(batches_dir: Path | None) -> list[QueuedBatch]:
    """Batches in queue order, each with the run specs its state has not started yet."""
    if batches_dir is None:
        return []
    directory = Path(batches_dir)
    try:
        found_paths = {path.stem: path for path in directory.glob("*.toml")}
    except OSError:
        return []
    damaged = None
    try:
        if _unparseable(directory / LEDGER_FILENAME):
            raise KarnError("queue_ledger_invalid")
        ledger = read_ledger(directory)
    except (KarnError, RecursionError) as error:
        # A damaged ledger reads as none, and stops every dispatch until it is repaired.
        ledger, damaged = (
            None,
            str(error) if isinstance(error, KarnError) else "queue_ledger_invalid",
        )
    paths = [found_paths[name] for name in queue_order(found_paths, ledger)]
    found = []
    for path in paths:
        batch_id = path.stem
        state_path = directory / "state" / (batch_id + ".json")
        try:
            if _unparseable(path):
                raise KarnError("batch_unreadable:" + path.name)
            batch = load_batch(path)
            if batch is None:
                found.append(QueuedBatch(batch_id, "legacy", None, 0, 0, ()))
                continue
            if _unparseable(state_path):
                raise KarnError("batch_state_invalid:" + batch_id)
            state = read_state(state_path, batch_id)
        except KarnError as error:
            found.append(QueuedBatch(batch_id, "error", None, 0, 0, (), str(error)))
            continue
        except (AttributeError, RecursionError):
            # The batch readers let a deeply nested file or a non-object state through.
            found.append(
                QueuedBatch(batch_id, "error", None, 0, 0, (), "batch_unreadable:" + path.name)
            )
            continue
        specs = batch["runs"]
        started = len(state["runs"]) if state else 0
        runs = tuple(
            QueuedRun(
                index,
                spec["benchmark"],
                spec["construct"],
                spec["build_output"],
                spec.get("budget_seconds", 86400),
                _candidate(spec["build_output"], spec["construct"]),
            )
            for index, spec in enumerate(specs)
            if index >= started
        )
        if state is None:
            status = "pending" if stateless_status(batch_id, ledger) == "pending" else "needs_ack"
        elif any(row["status"] == "running" for row in state["runs"]):
            status = "running"
        else:
            status = "pending" if runs else "done"
        error = None
        if damaged and status in ("pending", "needs_ack"):
            status, error = "ledger_damaged", damaged
        found.append(
            QueuedBatch(batch_id, status, batch.get("not_before"), started, len(specs), runs, error)
        )
    return found
