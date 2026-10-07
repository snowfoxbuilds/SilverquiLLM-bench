"""The run containers on this host's Docker daemon, read with ``ps`` and ``inspect`` only."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.karn.docker import RUN_LABEL

from ._read import instant, mapping

RUN_CONTAINER_PREFIX = "sq-run-"
DOCKER_TIMEOUT = 10
MAX_OUTPUT = 64 * 1024 * 1024


@dataclass(frozen=True)
class RunContainer:
    run_id: str
    name: str
    running: bool
    started_at: datetime | None
    finished_at: datetime | None
    run_dir: Path | None
    """The bind source of ``/workspace`` is ``<run-dir>/workspace``."""


Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _docker(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *arguments], capture_output=True, timeout=DOCKER_TIMEOUT, check=False
    )


def _container(row: dict) -> RunContainer | None:
    name = str(row.get("Name", "")).lstrip("/")
    run_id = mapping(mapping(row.get("Config")).get("Labels")).get(RUN_LABEL)
    if not isinstance(run_id, str) or name != RUN_CONTAINER_PREFIX + run_id:
        return None  # The run's proxy carries the same label.
    state = mapping(row.get("State"))
    run_dir = None
    for mount in row.get("Mounts") or []:
        mount = mapping(mount)
        if mount.get("Destination") == "/workspace" and isinstance(mount.get("Source"), str):
            source = Path(mount["Source"])
            run_dir = source.parent if source.name == "workspace" else None
    return RunContainer(
        run_id,
        name,
        state.get("Running") is True,
        instant(state.get("StartedAt")),
        instant(state.get("FinishedAt")),
        run_dir,
    )


def run_containers(docker: Runner = _docker) -> tuple[list[RunContainer], str | None]:
    """Every container a Karn run launched here, and why the list is unavailable if it is."""
    try:
        listed = docker(["ps", "-a", "-q", "--no-trunc", "--filter", "label=" + RUN_LABEL])
        if listed.returncode:
            return [], "docker_unavailable"
        ids = listed.stdout.decode(errors="replace").split()
        if not ids:
            return [], None
        inspected = docker(["container", "inspect", *ids])
    except (OSError, subprocess.TimeoutExpired):
        return [], "docker_unavailable"
    # A container removed between the two calls fails the inspect; the next poll sees it gone.
    if inspected.returncode and not inspected.stdout:
        return [], "docker_inspect_failed"
    if len(inspected.stdout) > MAX_OUTPUT:
        return [], "docker_inspect_failed"
    try:
        rows = json.loads(inspected.stdout)
    except (ValueError, RecursionError):
        return [], "docker_inspect_failed"
    found = (
        [_container(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    )
    return [container for container in found if container is not None], None
