"""Read-only views of the batch queue: ``silverquillm queue ls`` and ``top``.

Both read the batch files (desired state) and the scheduler's state files
(observed state) and never write either — the operator edits batch files in
``$EDITOR``; the scheduler owns ``batches/state/``.  ``queue ls`` is a
one-shot table; ``top`` redraws the same view on an interval in the
alternate screen until ``q``.  A malformed batch file is shown loudly in
both, as the scheduler skips it.
"""

from __future__ import annotations

import os
import select
import shutil
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from silverquillm.scheduler import (
    RUN_PENDING,
    Batch,
    BatchError,
    BatchState,
    StateError,
    batch_id_of,
    list_batch_files,
    load_batch,
    load_state,
    lock_status,
)

__all__ = [
    "BatchView",
    "QueueView",
    "RunRow",
    "build_queue_view",
    "render_queue",
    "run_top",
]

_ESC = "\x1b"
_STATE_ORDER = ("pending", "running", "done", "failed")


@dataclass(frozen=True)
class RunRow:
    """One line of a batch: a started run (from state) or a pending entry
    (from the file)."""

    index: int
    state: str
    candidate: str
    mode: str
    benchmark: str
    budget_seconds: int | str
    run_id: str = ""
    hash8: str = ""
    started_at: str = ""
    finished_at: str = ""
    note: str = ""


@dataclass
class BatchView:
    id: str
    path: Path
    not_before: str = ""
    due: bool = True
    error: str = ""
    runs: list[RunRow] = field(default_factory=list)
    recorded: int = 0
    in_file: int = 0

    @property
    def counts(self) -> dict[str, int]:
        counts = dict.fromkeys(_STATE_ORDER, 0)
        for row in self.runs:
            counts[row.state] = counts.get(row.state, 0) + 1
        return counts


@dataclass
class QueueView:
    batches_dir: Path
    generated_at: str
    scheduler_running: bool
    scheduler_holder: dict | None
    batches: list[BatchView] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        return self.batches_dir.is_dir()


def _rows(batch: Batch | None, state: BatchState) -> list[RunRow]:
    rows: list[RunRow] = []
    for run in state.runs:
        spec = run.spec
        rows.append(
            RunRow(
                index=run.index,
                state=run.state,
                candidate=str(spec.get("candidate", "?")),
                mode=str(spec.get("mode", "?")),
                benchmark=str(spec.get("benchmark", "?")),
                budget_seconds=spec.get("budget_seconds", "?"),
                run_id=run.run_id or "",
                hash8=run.hash8 or "",
                started_at=run.started_at or "",
                finished_at=run.finished_at or "",
                note=(run.error or run.summary or "").splitlines()[0] if (run.error or run.summary) else "",
            )
        )
    if batch is not None:
        for index in range(state.consumed, len(batch.runs)):
            spec = batch.runs[index]
            rows.append(
                RunRow(
                    index=index,
                    state=RUN_PENDING,
                    candidate=spec.candidate,
                    mode=spec.mode,
                    benchmark=spec.benchmark,
                    budget_seconds=spec.budget_seconds,
                )
            )
    return rows


def build_queue_view(batches_dir: Path, *, now: datetime | None = None) -> QueueView:
    """Read every batch file and state file under *batches_dir*; write nothing."""
    batches_dir = Path(batches_dir)
    moment = now or datetime.now(UTC)
    status = lock_status(batches_dir) if batches_dir.is_dir() else None
    view = QueueView(
        batches_dir=batches_dir,
        generated_at=moment.astimezone(UTC).isoformat(timespec="seconds"),
        scheduler_running=bool(status and status.held),
        scheduler_holder=status.holder if status and status.held else None,
    )
    for path in list_batch_files(batches_dir):
        batch_id = batch_id_of(path)
        item = BatchView(id=batch_id, path=path)
        batch: Batch | None
        try:
            batch = load_batch(path)
        except BatchError as exc:
            batch = None
            item.error = f"MALFORMED (skipped by the scheduler): {exc}"
        try:
            state = load_state(batches_dir, batch_id, batch_file=str(path))
        except StateError as exc:
            state = BatchState(batch=batch_id, batch_file=str(path))
            item.error = (item.error + "; " if item.error else "") + f"state unreadable: {exc}"
        if batch is not None:
            item.not_before = batch.not_before.astimezone(UTC).isoformat(timespec="seconds") if batch.not_before else ""
            item.due = batch.due(moment)
            item.in_file = len(batch.runs)
        item.recorded = state.consumed
        item.runs = _rows(batch, state)
        view.batches.append(item)
    return view


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def render_queue(view: QueueView, *, width: int | None = None) -> list[str]:
    """The one-shot table (also each ``top`` frame's body)."""
    width = width or shutil.get_terminal_size((120, 40)).columns
    if not view.exists:
        return [f"no batches directory at {view.batches_dir} — nothing queued"]
    if view.scheduler_running:
        holder = view.scheduler_holder or {}
        who = f"running (pid {holder.get('pid', '?')} on {holder.get('hostname', '?')} since {holder.get('started_at', '?')})"
    else:
        who = "not running"
    lines = [f"batches: {view.batches_dir}    scheduler: {who}    as of {view.generated_at}"]
    if not view.batches:
        lines.append("(no batch files)")
        return lines
    for item in view.batches:
        counts = item.counts
        due = "yes" if item.due else "no"
        header = (
            f"{item.id}  not_before={item.not_before or '-'} due={due}"
            f"  pending={counts['pending']} running={counts['running']}"
            f" done={counts['done']} failed={counts['failed']}"
        )
        if item.recorded > item.in_file and not item.error:
            header += f"  ({item.recorded} started, file now lists {item.in_file})"
        lines.append(_clip(header, width))
        if item.error:
            lines.append(_clip(f"  !! {item.error}", width))
        if not item.runs:
            lines.append("  (no runs)")
            continue
        lines.append("   #  STATE    CANDIDATE                              MODE     BENCHMARK   BUDGET  RUN")
        for row in item.runs:
            run = row.run_id + (f" [{row.hash8}]" if row.hash8 else "")
            if row.note and row.state in ("failed", "done"):
                run += f" — {row.note}"
            line = (
                f"  {row.index:>2}  {row.state:<8} {_clip(row.candidate, 38):<38} {row.mode:<8}"
                f" {row.benchmark:<11} {row.budget_seconds!s:>6}  {run}"
            )
            lines.append(_clip(line, width))
    return lines


# ---------------------------------------------------------------------------
# top
# ---------------------------------------------------------------------------


def _terminal_key_reader(interval: float) -> Callable[[], str | None]:
    fd = sys.stdin.fileno()

    def read_key() -> str | None:
        ready, _, _ = select.select([fd], [], [], interval)
        if not ready:
            return None
        return os.read(fd, 1).decode("utf-8", errors="replace")

    return read_key


def run_top(
    batches_dir: Path,
    *,
    interval: float = 2.0,
    out: TextIO | None = None,
    read_key: Callable[[], str | None] | None = None,
    now: Callable[[], datetime] | None = None,
    max_frames: int | None = None,
) -> int:
    """Redraw the queue view every *interval* seconds until ``q`` (or
    *max_frames*); returns the number of frames drawn.  Read-only: it never
    writes a batch file, a state file, or the lock.

    With a terminal on stdin the alternate screen is used and *read_key*
    defaults to a raw-mode key reader; tests inject *out*, *read_key*, *now*
    and *max_frames* to run frames without a terminal.
    """
    out = out or sys.stdout
    interactive = read_key is None and sys.stdin.isatty() and out.isatty()
    old_termios = None
    if interactive:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_termios = termios.tcgetattr(fd)
        tty.setraw(fd)
        out.write(f"{_ESC}[?1049h{_ESC}[?25l")
        read_key = _terminal_key_reader(interval)
    elif read_key is None:
        # No terminal: one frame, like `queue ls`.
        max_frames = 1 if max_frames is None else max_frames
        read_key = lambda: None

    stop = False

    def _stop(signum: int, frame: object) -> None:
        nonlocal stop
        stop = True

    old_handlers = {}
    if interactive:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, _stop)
    frames = 0
    try:
        while not stop:
            view = build_queue_view(batches_dir, now=now() if now else None)
            width = shutil.get_terminal_size((120, 40)).columns if interactive else None
            body = render_queue(view, width=width)
            header = f"silverquillm top — refresh {interval:g}s — q to quit"
            if interactive:
                out.write(f"{_ESC}[2J{_ESC}[H")
                out.write("\r\n".join([header, *body, ""]))
            else:
                out.write("\n".join([header, *body, ""]))
            out.flush()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
            key = read_key()
            if key in ("q", "Q", "\x03"):
                break
    finally:
        if interactive:
            import termios

            out.write(f"{_ESC}[?25h{_ESC}[?1049l")
            out.flush()
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_termios)
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
    return frames
