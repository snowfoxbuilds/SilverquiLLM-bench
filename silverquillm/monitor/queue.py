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
    read_control,
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
    """The ``queue ls`` vocabulary: ``pending``, ``running``, ``done``, ``missing_state`` (no state,
    and not new), ``ledger_damaged`` (the queue ledger stops every dispatch),
    ``unsupported_legacy_batch`` or ``error``."""
    not_before: datetime | None
    started: int
    total: int
    runs: tuple[QueuedRun, ...]
    error: str | None = None
    run_ids: tuple[str, ...] = ()
    """The run id of every entry the batch has started, in entry order."""

    @property
    def needs_ack(self) -> bool:
        return self.status == "missing_state"


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


def dispatch_mode(batches_dir: Path | None) -> str:
    """The queue's dispatch mode; an unreadable control file reads as paused, never running."""
    if batches_dir is None:
        return "running"
    return read_control(Path(batches_dir))["mode"]


def _ledger(directory: Path) -> tuple[list[dict] | None, str | None]:
    """The queue ledger's entries, and the error when it is damaged (then the entries are None)."""
    try:
        if _unparseable(directory / LEDGER_FILENAME):
            raise KarnError("queue_ledger_invalid")
        return read_ledger(directory), None
    except (KarnError, RecursionError) as error:
        # A damaged ledger reads as none, and stops every dispatch until it is repaired.
        return None, str(error) if isinstance(error, KarnError) else "queue_ledger_invalid"
    except OSError as error:
        return None, f"queue_ledger_unreadable:{type(error).__name__}"


def ledger_status(batches_dir: Path | None) -> tuple[str, str | None]:
    """``none`` before the scheduler first records a batch here, ``ok``, or ``damaged`` with
    the error that stops every dispatch."""
    if batches_dir is None:
        return "none", None
    entries, damaged = _ledger(Path(batches_dir))
    if damaged:
        return "damaged", damaged
    return ("none" if entries is None else "ok"), None


def queued_batches(batches_dir: Path | None) -> list[QueuedBatch]:
    """Batches in queue order, each with the run specs its state has not started yet."""
    if batches_dir is None:
        return []
    directory = Path(batches_dir)
    try:
        found_paths = {path.stem: path for path in directory.glob("*.toml")}
    except OSError:
        return []
    ledger, damaged = _ledger(directory)
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
                found.append(QueuedBatch(batch_id, "unsupported_legacy_batch", None, 0, 0, ()))
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
            status = "pending" if stateless_status(batch_id, ledger) == "pending" else "missing_state"
        elif any(row["status"] == "running" for row in state["runs"]):
            status = "running"
        else:
            status = "pending" if runs else "done"
        error = None
        if damaged and status in ("pending", "missing_state"):
            status, error = "ledger_damaged", damaged
        run_ids = tuple(row["run_id"] for row in state["runs"]) if state else ()
        found.append(
            QueuedBatch(
                batch_id,
                status,
                batch.get("not_before"),
                started,
                len(specs),
                runs,
                error,
                run_ids,
            )
        )
    return found
