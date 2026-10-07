"""Not-yet-started run specs of the batch queue, in the order the scheduler will run them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.karn.batching import load_batch, read_state
from silverquillm.karn.definition import KarnError

from ._read import read_json
from .candidates import CandidateDisplay, candidate_display


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
    """``pending``, ``running``, ``done``, ``needs_ack`` (no committed state), ``legacy`` or ``error``."""
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


def queued_batches(batches_dir: Path | None) -> list[QueuedBatch]:
    """Batches in name order, each with the run specs its state has not started yet."""
    if batches_dir is None:
        return []
    directory = Path(batches_dir)
    try:
        paths = sorted(directory.glob("*.toml"))
    except OSError:
        return []
    found = []
    for path in paths:
        batch_id = path.stem
        try:
            batch = load_batch(path)
            if batch is None:
                found.append(QueuedBatch(batch_id, "legacy", None, 0, 0, ()))
                continue
            state = read_state(directory / "state" / (batch_id + ".json"), batch_id)
        except KarnError as error:
            found.append(QueuedBatch(batch_id, "error", None, 0, 0, (), str(error)))
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
            status = "needs_ack"
        elif any(row["status"] == "running" for row in state["runs"]):
            status = "running"
        else:
            status = "pending" if runs else "done"
        found.append(
            QueuedBatch(batch_id, status, batch.get("not_before"), started, len(specs), runs)
        )
    return found
