"""Live Benchmark Runs on this host and the stage each is in (RUN-MONITORING.md, Run stages)."""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.karn.records import InvalidRunRecordError, KarnIdentity
from silverquillm.karn.subscription_usage import provider_for

from ._read import instant, mapping, read_json
from .candidates import CandidateDisplay, candidate_display
from .containers import RunContainer
from .locks import lock_held

RUN_ID_LIMIT = 64


class Stage(enum.Enum):
    STARTING = "starting"
    """The runner holds the run and is staging it; its container has not started."""
    RUNNING = "running"
    GRADING = "grading"
    NEEDS_RECOVER = "needs_recover"
    UNKNOWN = "unknown"
    """The lock table is unavailable, so whether a runner still owns the run is unknown."""


@dataclass(frozen=True)
class LiveRun:
    run_id: str
    run_dir: Path
    stage: Stage
    benchmark: str | None
    construct: str | None
    candidate: CandidateDisplay
    candidate_hash: str | None
    login_profile: str | None
    provider: str | None
    budget_seconds: int | None
    host_started_at: datetime | None
    container: RunContainer | None
    native_telemetry: bool
    telemetry_adapter: str | None

    @property
    def started_at(self) -> datetime | None:
        """The container's start, which the budget runs against; else the host's."""
        if self.container is not None and self.container.started_at is not None:
            return self.container.started_at
        return self.host_started_at

    def elapsed_seconds(self, now: datetime) -> float | None:
        """Container time: up to now while running, else up to the container's stop."""
        start = self.container.started_at if self.container else None
        if start is None:
            return None
        end = now if self.container.running else (self.container.finished_at or now)
        return max(0.0, (end - start).total_seconds())


def _stage(run_dir: Path, container: RunContainer | None, held) -> Stage:
    owned = lock_held(run_dir / ".runner.lock", held)
    if owned is None:
        return Stage.UNKNOWN
    if not owned:
        # A runner killed outright leaves its detached container running; nothing harvests it.
        return Stage.NEEDS_RECOVER
    if container is not None and container.running:
        return Stage.RUNNING
    if container is not None or (run_dir / "host" / "host-result.json").exists():
        return Stage.GRADING
    return Stage.STARTING


def _candidate(run_dir: Path, run_input: dict) -> tuple[CandidateDisplay, str | None]:
    construct = run_input.get("construct")
    definition = None
    if isinstance(construct, str) and construct and "/" not in construct and construct[0] != ".":
        definition = read_json(run_dir / "candidate" / "constructs" / construct / "definition.json")
    try:
        candidate_hash = KarnIdentity.from_dict(run_input.get("candidate_identity")).hash
    except InvalidRunRecordError:
        candidate_hash = None
    revision = mapping(run_input.get("provenance")).get("recipe_revision")
    return candidate_display(definition, candidate_hash, revision), candidate_hash


def _live_run(run_dir: Path, container: RunContainer | None, held) -> LiveRun | None:
    if (run_dir / "run-record.json").exists():
        return None
    run_input = read_json(run_dir / "run-input.json")
    if not isinstance(run_input, dict):
        if container is None:
            return None  # A run directory before its input is written, or not a run at all.
        run_input = {}
    candidate, candidate_hash = _candidate(run_dir, run_input)
    telemetry = mapping(run_input.get("native_telemetry"))
    adapter = telemetry.get("adapter") if isinstance(telemetry.get("adapter"), str) else None
    login = run_input.get("login") if isinstance(run_input.get("login"), str) else None
    budget = run_input.get("budget_seconds")
    return LiveRun(
        run_id=run_dir.name,
        run_dir=run_dir,
        stage=_stage(run_dir, container, held),
        benchmark=run_input.get("benchmark")
        if isinstance(run_input.get("benchmark"), str)
        else None,
        construct=run_input.get("construct")
        if isinstance(run_input.get("construct"), str)
        else None,
        candidate=candidate,
        candidate_hash=candidate_hash,
        login_profile=login,
        provider=provider_for(login, adapter),
        budget_seconds=budget if type(budget) is int else None,
        host_started_at=instant(run_input.get("started_at")),
        container=container,
        native_telemetry=telemetry.get("enabled") is True,
        telemetry_adapter=adapter,
    )


def _run_dirs(runs_dir: Path | None) -> list[Path]:
    if runs_dir is None:
        return []
    try:
        entries = list(os.scandir(runs_dir))
    except OSError:
        return []
    return [
        Path(entry.path)
        for entry in entries
        if len(entry.name) <= RUN_ID_LIMIT
        and not entry.name.startswith(".")
        and entry.is_dir(follow_symlinks=False)
    ]


def live_runs(runs_dir: Path | None, containers: list[RunContainer], held) -> list[LiveRun]:
    """Runs without a Run Record, from this host's run directory and its run containers.

    A container's own bind mount names its run directory, so a direct run started with
    another run directory is found too.
    """
    by_dir: dict[Path, RunContainer | None] = {path: None for path in _run_dirs(runs_dir)}
    for container in containers:
        run_dir = container.run_dir
        if run_dir is None and runs_dir is not None:
            run_dir = Path(runs_dir) / container.run_id
        if run_dir is not None and run_dir.name == container.run_id:
            by_dir[run_dir] = container
    found = []
    for run_dir, container in by_dir.items():
        run = _live_run(run_dir, container, held)
        if run is not None:
            found.append(run)
    # Runs needing recovery lead the running pane; the rest run oldest first.
    return sorted(
        found,
        key=lambda run: (
            run.stage is not Stage.NEEDS_RECOVER,
            run.started_at.timestamp() if run.started_at else float("inf"),
            run.run_id,
        ),
    )
