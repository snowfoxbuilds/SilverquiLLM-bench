"""What a run details view shows beyond a run's one-line summary (RUN-MONITORING.md).

A recorded run's requests and cost breakdown come from its Run Record; a run's Workspace tab
comes from its snapshot index and the agent's own commit log, read as a file: the workspace
repository is candidate-controlled, so no git command ever runs in it.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ._read import MAX_USD, instant, mapping, read_json
from .costs import RequestCost

MAX_REFLOG = 4 * 1024 * 1024
MAX_COMMITS = 500
COST_TYPES = ("uncached_input", "cache_read", "cache_write", "cache_write_1h", "output")


def _usd(value: Any) -> Decimal | None:
    if not isinstance(value, str | int) or isinstance(value, bool):
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and 0 <= amount <= MAX_USD else None


def _count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _rows(value: Any) -> list[dict]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


@dataclass(frozen=True)
class RecordDetail:
    requests: list[RequestCost]
    breakdown: dict[str, tuple[int | None, Decimal | None]]
    """Tokens and USD per input type, as the record's cost breakdown names them."""
    exit_code: int | None
    failure_stage: str | None
    error: str | None
    grading_source: str | None


def record_detail(record_dir: Path) -> RecordDetail | None:
    manifest = read_json(Path(record_dir) / "manifest.json")
    if not isinstance(manifest, dict):
        return None
    metadata = mapping(manifest.get("run_metadata"))
    measurements = mapping(metadata.get("measurements"))
    execution = mapping(metadata.get("execution"))
    prices = {
        row["response_id"]: _usd(row.get("usd"))
        for row in _rows(measurements.get("request_prices"))
        if isinstance(row.get("response_id"), str)
    }
    requests = []
    for row in _rows(measurements.get("requests")):
        stamp = _count(row.get("timestamp_ms"))
        response_id = row.get("response_id")
        usage = mapping(row.get("usage"))
        requests.append(
            RequestCost(
                stamp or 0,
                row.get("model") if isinstance(row.get("model"), str) else None,
                {key: _count(value) for key, value in usage.items() if isinstance(key, str)},
                prices.get(response_id) if isinstance(response_id, str) else None,
            )
        )
    requests.sort(key=lambda request: request.timestamp_ms)
    breakdown_value = mapping(mapping(measurements.get("cost_breakdown")).get("value"))
    breakdown = {
        name: (_count(mapping(cell).get("tokens")), _usd(mapping(cell).get("usd")))
        for name in COST_TYPES
        if isinstance(cell := breakdown_value.get(name), dict)
    }
    error = execution.get("error")
    grading = mapping(metadata.get("grading_source"))
    source = grading.get("kind") or grading.get("source") or grading.get("selected")
    return RecordDetail(
        requests,
        breakdown,
        execution.get("exit_code") if type(execution.get("exit_code")) is int else None,
        execution.get("failure_stage") if isinstance(execution.get("failure_stage"), str) else None,
        error if isinstance(error, str) else None,
        source if isinstance(source, str) else None,
    )


@dataclass(frozen=True)
class SnapshotEntry:
    captured_at: datetime | None
    kind: str
    files: int | None
    files_delta: int | None
    changed: bool
    """The workspace digest differs from the previous snapshot's."""
    retained: bool


@dataclass(frozen=True)
class CommitEntry:
    at: datetime | None
    action: str
    """The reflog's action, such as ``commit`` or ``commit (initial)`` or ``reset``."""
    message: str
    commit: str


@dataclass(frozen=True)
class WorkspaceView:
    snapshots: list[SnapshotEntry]
    commits: list[CommitEntry]


def _snapshots(run_dir: Path) -> list[SnapshotEntry]:
    entries, previous_digest, previous_files = [], None, None
    for row in _rows(read_json(run_dir / "snapshots.json")):
        digest = row.get("digest") if isinstance(row.get("digest"), str) else None
        files = _count(row.get("files"))
        entries.append(
            SnapshotEntry(
                instant(row.get("captured_at")),
                row.get("kind") if isinstance(row.get("kind"), str) else "?",
                files,
                files - previous_files
                if files is not None and previous_files is not None
                else None,
                previous_digest is not None and digest != previous_digest,
                row.get("retained") is True,
            )
        )
        previous_digest, previous_files = digest, files
    return entries


def _read_beneath(root: Path, parts: tuple[str, ...], limit: int) -> bytes | None:
    """A regular file under ``root``, opened without following any link on the way."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptors = []
    try:
        current = os.open(root, flags | os.O_DIRECTORY)
        descriptors.append(current)
        for part in parts[:-1]:
            current = os.open(part, flags | os.O_DIRECTORY, dir_fd=current)
            descriptors.append(current)
        handle = os.open(parts[-1], flags, dir_fd=current)
        with os.fdopen(handle, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                return None
            if info.st_size > limit:
                stream.seek(info.st_size - limit)
            return stream.read(limit)
    except OSError:
        return None
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def _commits(run_dir: Path) -> list[CommitEntry]:
    for workspace in ("workspace", "workspace_final"):
        data = _read_beneath(run_dir / workspace, (".git", "logs", "HEAD"), MAX_REFLOG)
        if data is not None:
            break
    else:
        return []
    commits = []
    for raw in data.decode("utf-8", errors="replace").splitlines()[-MAX_COMMITS:]:
        identity, tab, message = raw.partition("\t")
        fields = identity.split()
        if not tab or len(fields) < 4:
            continue
        try:
            at = datetime.fromtimestamp(int(fields[-2]), UTC)
        except (ValueError, OverflowError, OSError):
            at = None
        action, colon, text = message.partition(": ")
        commits.append(
            CommitEntry(at, action if colon else "", text if colon else message, fields[1][:12])
        )
    return commits


def workspace_view(run_dir: Path | None) -> WorkspaceView:
    if run_dir is None:
        return WorkspaceView([], [])
    run_dir = Path(run_dir)
    return WorkspaceView(_snapshots(run_dir), _commits(run_dir))
